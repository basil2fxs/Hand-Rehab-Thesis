"""Entry point. Run: python main.py"""
from __future__ import annotations

import argparse
import logging
import sys


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


def main() -> int:
    args = parse_args()
    from rehab.config import Config
    from rehab.utils import log as logutil
    try:
        cfg = Config.load(args.config)
    except FileNotFoundError as e:
        # Either default.yaml went missing (broken install) or the user
        # passed --config pointing at a non-existent file.
        print(f"Config file not found: {e}", file=sys.stderr)
        return 5
    except Exception as e:
        # Most likely a YAML parse error from a hand-edited override.
        print(f"Could not load config: {e}", file=sys.stderr)
        return 5
    logutil.setup(args.log_level or cfg.get("logging.level", "INFO"),
                  cfg.get("logging.file"))
    log = logging.getLogger("main")
    log.info("Config from %s", cfg.source)

    # CLI overrides
    if args.hand:
        cfg.data.setdefault("bilateral", {})["hand"] = args.hand
    if args.mode:
        cfg.data.setdefault("game", {})["mode"] = args.mode
    if args.participant:
        cfg.data.setdefault("session", {})["participant"] = args.participant

    if args.list_ports:
        from rehab.hardware.serial_source import list_available_ports
        for p in list_available_ports():
            vid = f"0x{p.vid:04x}" if p.vid is not None else "?"
            pid = f"0x{p.pid:04x}" if p.pid is not None else "?"
            print(f"{p.device:24s}  vid={vid}  pid={pid}  {p.description}")
        return 0

    source = _build_source(cfg, args)
    if source is None:
        log.error("Could not build any source. Try --source keyboard.")
        return 2

    from rehab.game.engine import GameEngine
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


def _resolve_ports_and_hands(cfg, fallback_ports):
    """Pick the (ports, hand_assignment) pair MultiSerialSource should
    use, honouring serial.left_port + serial.right_port overrides from
    the Settings screen.

    Behaviour:
      - Both overrides set -> exactly those two ports, right + left.
      - One override set -> that hand gets its assigned port; the other
        hand gets the first remaining detected port (if any), else
        falls back to a single-hand source.
      - Neither set -> use fallback_ports in plug order (default).
    """
    log = logging.getLogger("main")
    left = cfg.get("serial.left_port")
    right = cfg.get("serial.right_port")
    if not left and not right:
        return fallback_ports, None
    chosen: list[str] = []
    hands: list[str] = []
    if right:
        chosen.append(right)
        hands.append("right")
    if left:
        chosen.append(left)
        hands.append("left")
    if len(chosen) == 1:
        # The user pinned one hand; fill the other with any remaining
        # detected port so bilateral still works if both Arduinos are
        # plugged in but only one was explicitly assigned.
        remaining = [p for p in fallback_ports if p not in chosen]
        if remaining:
            chosen.append(remaining[0])
            hands.append("left" if "left" not in hands else "right")
    log.info("Using explicit port assignment: %s",
             list(zip(hands, chosen)))
    return chosen, hands


def _build_source(cfg, args):
    log = logging.getLogger("main")
    n_per_hand = int(cfg.get("fsr.num_sensors_per_hand", 4))

    def _make_multi(ports, hands):
        from rehab.hardware.multi_serial import MultiSerialSource
        return MultiSerialSource(
            ports=ports,
            baud=int(cfg.get("serial.baud", 115200)),
            num_sensors_per_hand=n_per_hand,
            read_timeout_s=float(cfg.get("serial.read_timeout_s", 0.02)),
            open_retries=int(cfg.get("serial.open_retries", 3)),
            retry_delay_s=float(cfg.get("serial.open_retry_delay_s", 1.0)),
            hand_assignment=hands,
        )

    chosen = args.source
    if chosen == "auto":
        try:
            from rehab.hardware.serial_source import (
                _HAVE_SERIAL, discover_ports,
            )
        except ImportError:
            _HAVE_SERIAL = False
        if _HAVE_SERIAL:
            # Discover up to two Arduinos. Aiden's firmware puts one
            # hand on each board, so bilateral training needs both
            # connected. Either-or-both is fine; the source class
            # only exposes the hand_modes it can actually drive.
            ports: list[str] = []
            forced = args.port or cfg.get("serial.port", "auto")
            if forced and forced != "auto":
                ports = [forced]
            else:
                ports = discover_ports(cfg.get("serial.vendor_ids"))
            ports, hands = _resolve_ports_and_hands(cfg, ports)
            if ports:
                try:
                    return _make_multi(ports, hands)
                except Exception as e:
                    log.warning("Could not open serial: %s", e)
        log.info("Falling back to keyboard mode")
        chosen = "keyboard"

    if chosen == "serial":
        from rehab.hardware.serial_source import discover_ports
        if args.port:
            ports = [args.port]
        else:
            ports = discover_ports(cfg.get("serial.vendor_ids"))
        ports, hands = _resolve_ports_and_hands(cfg, ports)
        if not ports:
            return None
        try:
            return _make_multi(ports, hands)
        except Exception as e:
            log.error("Serial unavailable: %s", e)
            return None

    if chosen == "keyboard":
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        return KeyboardOnlySource()

    return None


if __name__ == "__main__":
    sys.exit(main())
