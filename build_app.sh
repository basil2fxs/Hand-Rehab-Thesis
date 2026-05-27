#!/usr/bin/env bash
# Build the standalone app for the current platform (macOS or Linux).
# Result lands in bin/dist/. Build intermediates go to bin/build/ so
# the project root stays clean.

set -euo pipefail

cd "$(dirname "$0")"

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
    echo
    echo "macOS .app bundle: bin/dist/Finger Rehab.app"
    echo "Double-click it from Finder, or run from terminal:"
    echo "  open 'bin/dist/Finger Rehab.app'"
else
    echo
    echo "Linux binary: bin/dist/Finger Rehab/Finger Rehab"
    echo "Run it with:"
    echo "  ./bin/dist/Finger\\ Rehab/Finger\\ Rehab"
fi
