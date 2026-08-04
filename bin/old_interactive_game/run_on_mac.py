"""Mac-friendly launcher for Aiden's rhythm_game.py.

His source file sets `os.environ['SDL_VIDEODRIVER'] = 'windib'` on
import (line 6), which is Windows-only and prevents the pygame window
from opening on macOS. It also assumes COM7 (Windows serial port name)
for the FSR sensor; that path is already wrapped in a try/except so a
serial failure just enables keyboard fallback, no crash.

This launcher reads the source, patches the windib line out so SDL
picks the macOS default driver (cocoa), and executes the game in this
folder so its `resources/` and `data/` sub-folders resolve correctly.

Run from a Mac terminal:
    python3 run_on_mac.py

Keyboard fallback: 1 2 3 4 fire the four lanes.
Quit: window close button.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    here = Path(__file__).resolve().parent
    src_path = here / "rhythm_game.py"
    if not src_path.exists():
        print(f"Could not find {src_path}", file=sys.stderr)
        return 1

    src = src_path.read_text(encoding="utf-8")
    needle = "os.environ['SDL_VIDEODRIVER'] = 'windib'"
    if needle not in src:
        print("Heads up: the windib line wasn't found. Source layout may "
              "have changed - check rhythm_game.py and update this runner.",
              file=sys.stderr)
    # Replace with a no-op so SDL falls back to the platform default.
    # Setting it to an empty string would mean "no video driver"; deleting
    # any prior value via pop() keeps the env clean if something earlier
    # in the shell already set it.
    patch = (
        "os.environ.pop('SDL_VIDEODRIVER', None)  "
        "# patched for macOS: let SDL pick (cocoa)"
    )
    src = src.replace(needle, patch, 1)

    # Run from the InteractiveGame folder so resources/ and data/ paths
    # resolve. __file__ is set to the original path so any internal
    # references to it (e.g. logging the script name) stay sensible.
    os.chdir(here)
    code = compile(src, str(src_path), "exec")
    namespace = {"__name__": "__main__", "__file__": str(src_path)}
    exec(code, namespace)
    return 0


if __name__ == "__main__":
    sys.exit(main())
