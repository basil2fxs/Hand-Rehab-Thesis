#!/bin/bash
# Double-click launcher for the Finger Rehab app.
# Finder runs this in Terminal. It changes into its own folder (so it
# works wherever the project lives), finds a working python3, and starts
# the game. Any error stays on screen so it can be read rather than the
# window vanishing.

# cd to the folder this script lives in, whatever it is called or wherever
# it was copied to.
cd "$(dirname "$0")" || exit 1

echo "Starting Finger Rehab..."
echo

# Finder launches with a minimal PATH that often misses python3, so look in
# the usual install spots as well as whatever PATH does provide.
PY=""
for cand in \
    "$(command -v python3 2>/dev/null)" \
    /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3 \
    /usr/bin/python3 ; do
    if [ -n "$cand" ] && [ -x "$cand" ]; then
        PY="$cand"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "Could not find python3 on this Mac."
    echo "Install Python 3 from https://www.python.org/downloads/ and try again."
    echo
    echo "Press Return to close this window."
    read -r _
    exit 1
fi

# Run the app. If it exits with an error, hold the window open so the
# message can be read.
"$PY" main.py
status=$?

if [ "$status" -ne 0 ]; then
    echo
    echo "Finger Rehab exited with an error (code $status)."
    echo "If it mentions a missing module, run this once in Terminal:"
    echo "    $PY -m pip install -r requirements.txt"
    echo
    echo "Press Return to close this window."
    read -r _
fi
