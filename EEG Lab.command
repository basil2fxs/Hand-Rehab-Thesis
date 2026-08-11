#!/bin/bash
# Double-click launcher for EEG lab sessions. Runs the SAME main.py as
# "Finger Rehab.command" with the lab overlay on top of the defaults:
# markers on, trigger box required, fixed-foreperiod reaction variant.
# There is no separate lab build; the config file is the whole
# difference.

cd "$(dirname "$0")" || exit 1

echo "Starting Finger Rehab (EEG lab mode)..."
echo

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

"$PY" main.py --config config/eeg_lab.yaml
status=$?

if [ "$status" -ne 0 ]; then
    echo
    echo "EEG lab mode exited with an error (code $status)."
    echo "If it says the trigger port could not be opened, plug the"
    echo "trigger box in and check eeg.port in config/eeg_lab.yaml."
    echo
    echo "Press Return to close this window."
    read -r _
fi
