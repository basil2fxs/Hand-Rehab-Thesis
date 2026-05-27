"""Logger setup so the rest of the code can just call logging.getLogger."""
from __future__ import annotations

import logging
import sys
from pathlib import Path


_done = False


def setup(level: str = "INFO", file: str | None = None) -> None:
    global _done
    if _done:
        return
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if file:
        # Make sure the log dir exists before opening the handler.
        Path(file).parent.mkdir(parents=True, exist_ok=True)
        try:
            handlers.append(logging.FileHandler(file, encoding="utf-8"))
        except OSError as e:
            print(f"[log] could not open log file {file}: {e}", file=sys.stderr)
    logging.basicConfig(
        level=getattr(logging, str(level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )
    _done = True
