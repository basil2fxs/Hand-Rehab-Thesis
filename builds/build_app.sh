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

# Keep the EEG lab package current with every build. The config and
# setup notes always refresh from their sources of truth; the exe can
# only be built on Windows (or by CI), so pass a local Windows build
# through when one is on hand and say so when it is not.
mkdir -p docs/lab_package
cp -f config/eeg_lab.yaml docs/lab_package/eeg_lab.yaml
cp -f docs/eeg_lab_setup.txt docs/lab_package/eeg_lab_setup.txt
if [[ -f "builds/Windows/Finger Rehab.exe" ]]; then
    cp -f "builds/Windows/Finger Rehab.exe" "docs/lab_package/Finger Rehab.exe"
    echo "Lab package refreshed: docs/lab_package (copy the whole folder to the lab PC)"
else
    echo "Lab package: config and notes refreshed; no builds/Windows/Finger Rehab.exe here, get the exe from build_app.bat or the CI zip"
fi
