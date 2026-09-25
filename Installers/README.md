# Installers

| Folder | File | To install |
| --- | --- | --- |
| [`Windows/`](Windows) | `FingerRehab-Setup-Windows.exe` | Run it. It installs for this user with no administrator, and turns auto-start on |
| [`macOS/`](macOS) | `FingerRehab-macOS.dmg` | Open it and drag Finger Rehab into Applications |

Neither installer is signed, so the first open needs one click through. Windows: "Windows protected your PC",
More info, Run anyway. macOS: System Settings, Privacy & Security, Open Anyway.

The installers are not kept in git: each is about 250 MB. Take them from the latest
[build-apps run](https://github.com/basil2fxs/Hand-Rehab-Thesis/actions/workflows/build-apps.yml) (Artifacts),
or build them with `app/builds/build_app.bat` on Windows or `app/builds/build_app.sh` on a Mac.

<sub>[Back to the main README](../README.md)</sub>
