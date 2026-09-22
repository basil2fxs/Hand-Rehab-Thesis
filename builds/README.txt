Finger Rehab, installers
========================

Windows/  FingerRehab-Setup-Windows.exe   run it: installs per user under
                                          %LOCALAPPDATA%\Programs, no admin,
                                          and turns auto-start on
          Finger Rehab.exe                the same game, bare
Mac/      FingerRehab-macOS.dmg           open, drag Finger Rehab to Applications
          Finger Rehab.app                the same app, bare

Neither is signed, so the first open needs one click through.
Windows: "Windows protected your PC", More info, Run anyway.
Mac: System Settings, Privacy & Security, Open Anyway.

Session data goes to sessions/ next to the app, or to ~/Finger Rehab Data
when that folder cannot be written.

Rebuild after changing the source: build_app.bat on Windows (Python 3.12,
Inno Setup 6 for the installer) or build_app.sh on a Mac. Both drop their
files here and refresh docs/lab_package, the folder that goes to the lab.
The build-apps run on GitHub makes the same two installers plus
FingerRehab-EEGLab.zip.
