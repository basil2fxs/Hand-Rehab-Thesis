"""Print the app version: SOFTWARE_VERSION from finger_rehab/data/session.py.

One number for the session metadata, the macOS bundle, the Windows
installer and the CI artefacts. Read with a regex rather than imported
so a build machine needs nothing but Python to ask for it.
"""
import re
import sys
from pathlib import Path


def read_version() -> str:
    src = Path(__file__).resolve().parents[1] / "finger_rehab" / "data" / "session.py"
    m = re.search(r'^SOFTWARE_VERSION\s*=\s*"([^"]+)"', src.read_text(), re.M)
    if not m:
        raise SystemExit("SOFTWARE_VERSION not found in " + str(src))
    return m.group(1)


if __name__ == "__main__":
    sys.stdout.write(read_version() + "\n")
