# builds

Build scripts. Run them from `app/`. CI builds the same things on every push to `main`, so a local build is only needed to try a change on a real machine before it is pushed.

| Script | Makes | Needs |
| --- | --- | --- |
| `build_app.sh` | On a Mac: `Mac/FingerRehab-macOS.dmg` and the bare `Finger Rehab.app`; on Linux, `Linux/Finger Rehab` | Python with `requirements.txt` installed |
| `build_app.bat` | On Windows: `Windows/FingerRehab-Setup-Windows.exe` and the bare `Finger Rehab.exe` | Python 3.12 and, for the installer, Inno Setup 6 |
| `build_firmware.py` | The board firmware in `assets/firmware/`, with a checksum for each hex | PlatformIO |
| `fetch_avrdude.py` | The bundled uploader in `tools/avrdude/`, checked against Arduino's published checksums | An internet connection |
| `release_notes.py` | The text of each GitHub release | Run by CI |
| `version.py` | Prints `SOFTWARE_VERSION`, the one version number for the app, the installer and every session's metadata | Run by the build scripts and CI |

Each build script goes through the same steps. It rebuilds the firmware and fetches avrdude (neither stops the build: the hexes already staged are used, and a missing avrdude only means the app says so), wipes `bin/`, runs PyInstaller with `finger_rehab.spec` into `bin/dist/`, wraps the result (a disk image with an Applications link on a Mac, an Inno Setup installer on Windows from `installers/windows.iss`), and copies it into `builds/Mac/` or `builds/Windows/`. Last, both refresh `EEG_Lab`, the folder that goes to the lab, through `scripts/build_lab_package.py`; the exe in it can only come from a Windows build. None of the built files go into git.

CI makes the same two installers plus `FingerRehab-EEGLab.zip` and, when the tests pass, publishes all three as the release for `SOFTWARE_VERSION` in `finger_rehab/data/session.py`. Raise that number, and the two matching strings in `finger_rehab.spec`, to start a new release.

Neither installer is signed, so the first open needs one click through. Windows: "Windows protected your PC", More info, Run anyway. macOS: System Settings, Privacy & Security, Open Anyway.
