#!/usr/bin/env bash
# Build the app for the current platform (macOS or Linux).
# PyInstaller output goes to bin/dist/ (intermediates in bin/build/).
# On macOS the app is then wrapped in a disk image and both are copied
# into builds/Mac/, so the deliverables always live in one place.

set -euo pipefail

# The script lives in builds/; the build runs from the project root.
cd "$(dirname "$0")/.."

# Install build dependency if missing. Doesn't touch your existing venv.
python3 -m pip install --quiet --upgrade pyinstaller

# Firmware and avrdude, so Settings can flash the Arduino from the
# finished app. Neither may abort the build: a machine without
# PlatformIO keeps whatever hexes are already staged, and a failed
# download only means the app says avrdude is missing.
python3 builds/build_firmware.py || echo "Firmware not rebuilt; using what is staged."
python3 builds/fetch_avrdude.py || echo "avrdude not fetched; the app will say so."

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
    # The disk image: the app plus an Applications link to drag it
    # onto. UDZO is compressed and read-only. -ov replaces last time's.
    STAGE="bin/dist/dmg"
    rm -rf "$STAGE"
    mkdir -p "$STAGE"
    cp -R "bin/dist/Finger Rehab.app" "$STAGE/"
    ln -s /Applications "$STAGE/Applications"
    hdiutil create -volname "Finger Rehab" -srcfolder "$STAGE" \
        -ov -format UDZO "bin/dist/FingerRehab-macOS.dmg"
    rm -rf "$STAGE"
    # Refresh the ready-to-run copies in builds/Mac/.
    mkdir -p "builds/Mac"
    rm -rf "builds/Mac/Finger Rehab.app"
    cp -R "bin/dist/Finger Rehab.app" "builds/Mac/Finger Rehab.app"
    cp -f "bin/dist/FingerRehab-macOS.dmg" "builds/Mac/FingerRehab-macOS.dmg"
    echo
    echo "Installer: builds/Mac/FingerRehab-macOS.dmg"
    echo "Ready to run: builds/Mac/Finger Rehab.app"
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
