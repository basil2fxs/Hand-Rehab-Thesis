# Installers

The two installers go here, from the [latest release](https://github.com/basil2fxs/Hand-Rehab-Thesis/releases/latest) or a local build. Neither is kept in git: each is hundreds of MB. Each carries the game, its own Python and every library, so the computer it goes on needs nothing else installed.

| File | Goes in | To install | Built by |
| --- | --- | --- | --- |
| `FingerRehab-Setup-Windows.exe` | `Windows/` | Run it. No administrator needed | `app\builds\build_app.bat` |
| `FingerRehab-macOS.dmg` | `macOS/` | Open it and drag Finger Rehab into Applications | `app/builds/build_app.sh` |

Neither is signed, so the first open needs one click through. Windows: More info, Run anyway. macOS: System Settings, Privacy & Security, Open Anyway.

What each one sets up:

- **Windows** installs for the current user into `%LOCALAPPDATA%\Programs\Finger Rehab`, adds a Start menu shortcut (and a desktop one if ticked), and registers the auto-start watcher as a scheduled task, `FingerRehabAutostart`. Uninstalling removes the task too.
- **macOS** registers the watcher the first time the app opens from Applications. Opened straight from the disk image, it runs but leaves auto-start alone and says to drag it into Applications first.

Recordings go beside the app, or to `~/Finger Rehab Data` when it can't write there; Settings, Data, Open data folder shows which. Take both installers from the same release as `FingerRehab-EEGLab.zip`, so all three are one build.
