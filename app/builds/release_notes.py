"""Print the notes for a GitHub release: what each file is for.

The build-apps workflow calls this when it publishes a release, so the
notes are the same every time and live in the repo rather than in the
workflow. Plain ASCII, like every other file a person reads here.

Usage: python3 builds/release_notes.py VERSION COMMIT
"""
from __future__ import annotations

import sys
import time

REPO = "https://github.com/basil2fxs/Hand-Rehab-Thesis"
FILES = (
    ("FingerRehab-Setup-Windows.exe",
     "Windows 10 or 11. Run it; it doesn't need administrator rights. "
     'The first time, Windows shows "Windows protected your PC": click '
     "More info, then Run anyway."),
    ("FingerRehab-macOS.dmg",
     "macOS. Open it and drag Finger Rehab to Applications. The first "
     "time it's opened, allow it in System Settings, Privacy & Security, "
     "Open Anyway."),
    ("FingerRehab-EEGLab.zip",
     "The EEG lab PC. Unzip it, open run_in_psychopy.py in PsychoPy "
     "Coder and press Run."),
)


def notes(version: str, commit: str, when: str | None = None) -> str:
    when = when or time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    short = commit[:7]
    rows = "\n".join(f"| `{name}` | {what} |" for name, what in FILES)
    return (
        f"Finger Rehab {version}, built from commit [{short}]({REPO}/commit/"
        f"{commit}) on {when}, after all the tests passed.\n\n"
        f"| File | What it's for |\n| --- | --- |\n{rows}\n\n"
        f"These files are replaced each time version {version} is rebuilt, "
        f"so they always come from the newest build. What changed is in "
        f"the [commit history]({REPO}/commits/main), and the setup steps "
        f"are in the [README]({REPO}#install).\n")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write(__doc__.split("Usage: ")[1])
        return 2
    sys.stdout.write(notes(argv[1], argv[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
