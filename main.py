"""Entry point. Run: python main.py"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Finger rehab game")
    p.add_argument("--config", default=None,
                   help="Path to a YAML config that overrides defaults")
    p.add_argument("--source", default="auto",
                   choices=["auto", "serial", "keyboard"],
                   help="Sample source. 'auto' tries serial first.")
    p.add_argument("--port", default=None,
                   help="Override the serial port (skips auto-detect)")
    p.add_argument("--list-ports", action="store_true",
                   help="Print discovered serial ports and exit")
    p.add_argument("--hand", default=None,
                   choices=["left", "right", "both"],
                   help="Override the hand mode set in config")
    p.add_argument("--mode", default=None,
                   choices=["classic", "adaptive", "rhythm"],
                   help="Override the game mode set in config")
    p.add_argument("--participant", default=None)
    p.add_argument("--log-level", default=None,
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args()


def _sibling_lab_config() -> Path | None:
    """Return eeg_lab.yaml sitting next to the frozen executable, if any.

    The lab package (docs/lab_package) ships the exe with eeg_lab.yaml
    in the same folder. Double-clicking the exe passes no --config, and
    a plain run from that folder used to mean the standard game with
    markers off: exactly the silent failure lab mode exists to prevent.
    So a frozen exe treats a sibling eeg_lab.yaml as if --config had
    named it. Source runs never auto-load anything; the launchers pass
    --config explicitly and dev runs stay on the defaults.
    """
    if not getattr(sys, "frozen", False):
        return None
    exe = Path(sys.executable).resolve()
    here = exe.parent
    # On macOS the executable is buried inside Foo.app/Contents/MacOS;
    # the config would sit next to the .app the user sees, not in there.
    for parent in exe.parents:
        if parent.name.endswith(".app"):
            here = parent.parent
            break
    candidate = here / "eeg_lab.yaml"
    return candidate if candidate.is_file() else None


def main() -> int:
    args = parse_args()
    from finger_rehab.config import Config
    from finger_rehab.utils import log as logutil
    config_path = args.config
    if config_path is None:
        config_path = _sibling_lab_config()
    try:
        cfg = Config.load(config_path)
    except FileNotFoundError as e:
        # Either default.yaml went missing (broken install) or the user
        # passed --config pointing at a non-existent file.
        print(f"Config file not found: {e}", file=sys.stderr)
        return 5
    except Exception as e:
        # Most likely a YAML parse error from a hand-edited override.
        print(f"Could not load config: {e}", file=sys.stderr)
        return 5
    # Resolve the log path through the config so a relative
    # "sessions/finger_rehab.log" lands next to the app (USER_ROOT) instead of
    # whatever the working directory happens to be. Finder launches the
    # frozen .app with CWD=/ where a relative mkdir would fail.
    log_file = cfg.get("logging.file")
    if log_file:
        log_file = str(cfg.resolve_path(log_file))
    logutil.setup(args.log_level or cfg.get("logging.level", "INFO"),
                  log_file)
    log = logging.getLogger("main")
    log.info("Config from %s", cfg.source)
    if args.config is None and config_path is not None:
        log.info("Found eeg_lab.yaml next to the app; running in "
                 "EEG lab mode")

    # CLI overrides
    if args.hand:
        cfg.data.setdefault("bilateral", {})["hand"] = args.hand
    if args.mode:
        cfg.data.setdefault("game", {})["mode"] = args.mode
    if args.participant:
        cfg.data.setdefault("session", {})["participant"] = args.participant

    if args.list_ports:
        from finger_rehab.hardware.serial_source import list_available_ports
        for p in list_available_ports():
            vid = f"0x{p.vid:04x}" if p.vid is not None else "?"
            pid = f"0x{p.pid:04x}" if p.pid is not None else "?"
            print(f"{p.device:24s}  vid={vid}  pid={pid}  {p.description}")
        return 0

    source = _build_source(cfg, args)
    if source is None:
        log.error("Could not build any source. Try --source keyboard.")
        return 2

    from finger_rehab.game.engine import GameEngine
    try:
        engine = GameEngine(cfg, source)
    except Exception as e:
        # If construction blows up (bad theme name, malformed resolution,
        # missing FSR section) we should release the source we just opened
        # instead of leaving the Arduino in an open state.
        log.error("Could not build GameEngine: %s", e)
        try:
            source.stop()
        except Exception:
            pass
        return 6
    return engine.run()


def _build_source(cfg, args):
    """Pick the sample source for this run.

    The serial path delegates wholly to
    finger_rehab.hardware.discovery.build_source_from_config, the same
    builder the Settings screen's live reconnect uses, so the startup
    rules and the reconnect rules cannot drift apart. They used to be
    the same rules written twice, and only one copy was ever updated.
    Plug order assigns the first detected board to the RIGHT hand and
    the second to the LEFT; Settings overrides win only while the port
    they name still exists.
    """
    log = logging.getLogger("main")

    chosen = args.source
    if chosen in ("auto", "serial"):
        from finger_rehab.hardware.discovery import build_source_from_config
        source = None
        try:
            source = build_source_from_config(cfg, forced_port=args.port)
        except Exception as e:
            log.warning("Could not open serial: %s", e)
        if source is not None:
            return source
        if chosen == "serial":
            log.error("Serial unavailable: no usable port found")
            return None
        log.info("Falling back to keyboard mode")
        chosen = "keyboard"

    if chosen == "keyboard":
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        return KeyboardOnlySource()

    return None


if __name__ == "__main__":
    sys.exit(main())
