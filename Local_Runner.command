#!/bin/bash
# Local_Runner: starts the game on this Mac. Double-click it.
#
# The normal game, straight from the code in app/, so it is always the
# newest version there is: no build to wait for, no EEG. This Mac never
# has an EEG, so the lab settings (eeg_lab.yaml) are never loaded here;
# they live in the EEG_Lab folder, which goes to the lab.
#
# Recordings go to the sessions/ folder beside this file, which is the
# one the analysis notebook reads. Your calibration and settings stay
# in app/config as before.

set -e
cd "$(dirname "$0")/app"

# Prefer the Python that built the app, fall back to whatever is on the
# path, so this keeps working if that framework install ever moves.
PY="/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"
if [ ! -x "$PY" ]; then
    PY="$(command -v python3 || true)"
fi
if [ -z "$PY" ]; then
    echo "No python3 found. Install Python 3, then double-click this again."
    read -r -p "Press return to close." _
    exit 1
fi

echo "Starting Finger Rehab. Close the game window to stop."
echo "Recordings go to $(cd .. && pwd)/sessions"
echo

set +e
"$PY" main.py --data-dir ../sessions "$@"
STATUS=$?
set -e

echo
if [ $STATUS -ne 0 ]; then
    echo "The game exited with code $STATUS. The log is sessions/rehab.log."
    read -r -p "Press return to close." _
fi
exit $STATUS
