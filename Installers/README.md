# Installers

The two installers go here, from the [latest release](https://github.com/basil2fxs/Hand-Rehab-Thesis/releases/latest) or a local build. Neither is kept in git: each is hundreds of MB.

| File | Goes in | To install |
| --- | --- | --- |
| `FingerRehab-Setup-Windows.exe` | `Windows/` | Run it. No administrator needed; auto-start is on. Built by `app\builds\build_app.bat` |
| `FingerRehab-macOS.dmg` | `macOS/` | Open it and drag Finger Rehab into Applications. Built by `app/builds/build_app.sh` |

Neither is signed, so the first open needs one click through. Windows: More info, Run anyway. macOS: System Settings, Privacy & Security, Open Anyway.

Take both from the same release as `FingerRehab-EEGLab.zip`, so all three are one build.
