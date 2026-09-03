#!/usr/bin/env bash
# Build the standalone app for the current platform (macOS or Linux).
# PyInstaller output goes to bin/dist/ (intermediates in bin/build/),
# then the finished app is copied into builds/Mac/ so the ready-to-run
# deliverables always live in one obvious place at the project root.

set -euo pipefail

# The script lives in builds/; the build runs from the project root.
cd "$(dirname "$0")/.."

# Install build dependency if missing. Doesn't touch your existing venv.
python3 -m pip install --quiet --upgrade pyinstaller

# Clean previous build so stale data files don't sneak in.
rm -rf bin/build bin/dist
mkdir -p bin

python3 -m PyInstaller \
    --noconfirm \
    --workpath bin/build \
    --distpath bin/dist \
    finger_rehab.spec

echo
echo "Build complete. Artefacts:"
ls -1 bin/dist/

if [[ "$(uname)" == "Darwin" ]]; then
    # Refresh the ready-to-run copy in builds/Mac/.
    mkdir -p "builds/Mac"
    rm -rf "builds/Mac/Finger Rehab.app"
    cp -R "bin/dist/Finger Rehab.app" "builds/Mac/Finger Rehab.app"
    echo
    echo "Ready to run: builds/Mac/Finger Rehab.app"
    echo "Double-click it from Finder, or run from terminal:"
    echo "  open 'builds/Mac/Finger Rehab.app'"
else
    mkdir -p "builds/Linux"
    cp -f "bin/dist/Finger Rehab" "builds/Linux/Finger Rehab"
    echo
    echo "Ready to run: builds/Linux/Finger Rehab"
fi

# Keep the EEG lab package (docs/lab_package) current with every
# build: scripts/build_lab_package.py refreshes eeg_lab.yaml, rebuilds
# source/ and clears old text files. The exe can only be built on
# Windows (or by CI), so pass a local Windows build through when one
# is on hand; otherwise the exe already in the folder stays.
if [[ -f "builds/Windows/Finger Rehab.exe" ]]; then
    python3 scripts/build_lab_package.py --exe "builds/Windows/Finger Rehab.exe"
else
    python3 scripts/build_lab_package.py
fi
echo "Copy the whole docs/lab_package folder to the lab PC."
