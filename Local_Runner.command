#!/bin/bash
# Local_Runner: starts the EEG build on this Mac. Double-click it.
#
# Same software the lab gets, same markers, same lab settings. The one
# difference is that it does not insist on the trigger box, so with no
# box on the desk the markers go to the dummy backend and are still
# written to raw.csv. Plug a box in and it uses it.
#
# Everything else stays as it is: two deliverables, the installer for
# people at home and the lab folder for the lab. This file is the local
# way in, so nothing here has to be typed.

set -e
# The code lives in app/; this file sits above it so the top level
# stays to the point: the notebook, the sessions, the two things
# people are handed, and this.
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

echo "Starting the EEG build. Close the game window to stop."
echo "No trigger box here, so markers go to the dummy backend and are"
echo "still written to raw.csv. With a box plugged into this Mac, pass"
echo "its port:  ./Local_Runner.command --eeg-port /dev/cu.usbmodemXXXX"
echo

"$PY" main.py --config config/eeg_lab.yaml --no-eeg-box "$@"
STATUS=$?

echo
if [ $STATUS -ne 0 ]; then
    echo "The game exited with code $STATUS. The log is in sessions/."
    read -r -p "Press return to close." _
fi
exit $STATUS
