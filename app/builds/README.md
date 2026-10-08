# builds

Build scripts. Run from `app/`.

| Script | Makes |
| --- | --- |
| `build_app.sh` | On a Mac: `Mac/FingerRehab-macOS.dmg` and the bare `Finger Rehab.app` |
| `build_app.bat` | On Windows (Python 3.12, Inno Setup 6): `Windows/FingerRehab-Setup-Windows.exe` and the bare `Finger Rehab.exe` |
| `build_firmware.py` | The board firmware in `assets/firmware/` (needs PlatformIO) |
| `fetch_avrdude.py` | The bundled uploader in `tools/avrdude/` |
| `release_notes.py` | The text of each GitHub release |

Both build scripts also refresh `EEG_Lab`, the folder that goes to the lab. CI makes the same two installers plus `FingerRehab-EEGLab.zip` and, when the tests pass, publishes all three as the release for `SOFTWARE_VERSION` in `finger_rehab/data/session.py`. Raise that number to start a new release.

Neither installer is signed, so the first open needs one click through. Windows: "Windows protected your PC", More info, Run anyway. macOS: System Settings, Privacy & Security, Open Anyway.
