# Installers

Put the two installers here, from the [latest release](https://github.com/basil2fxs/Hand-Rehab-Thesis/releases/latest) or a local build. They aren't kept in git because each one is hundreds of MB. Each installer includes the game, its own Python and every library, so nothing else has to be installed on the computer.

| File | Goes in | To install | Built by |
| --- | --- | --- | --- |
| `FingerRehab-Setup-Windows.exe` | `Windows/` | Run it. No administrator needed | `app\builds\build_app.bat` |
| `FingerRehab-macOS.dmg` | `macOS/` | Open it and drag Finger Rehab into Applications | `app/builds/build_app.sh` |

Neither is signed, so each one has to be allowed the first time it's opened. On Windows click More info, then Run anyway. On macOS go to System Settings, Privacy & Security, Open Anyway.

What each one sets up:

- **Windows** installs for the current user into `%LOCALAPPDATA%\Programs\Finger Rehab`, adds a Start menu shortcut (and a desktop one if ticked), and registers the auto-start watcher as a scheduled task, `FingerRehabAutostart`. Uninstalling removes the task too.
- **macOS** registers the watcher the first time the app opens from Applications. If it's opened straight from the disk image it still runs, but it doesn't set up auto-start and asks to be dragged into Applications first.

Recordings are saved beside the app, or in `~/Finger Rehab Data` when it can't write there. Settings, Data, Open data folder shows which one is in use. Take both installers from the same release as `FingerRehab-EEGLab.zip`, so all three come from the same build.
