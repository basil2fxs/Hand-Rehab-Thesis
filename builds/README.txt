Finger Rehab, installers and ready-to-run apps
==============================================

Mac/      FingerRehab-macOS.dmg           open, drag Finger Rehab to Applications
          Finger Rehab.app                the same app, bare
Windows/  FingerRehab-Setup-Windows.exe   run it; installs per user, no admin
          Finger Rehab.exe                the same game, bare

Self-contained: Python and every library ship inside. The installer
turns auto-start on, so the game opens when a board is plugged in.
Session data goes to a sessions/ folder next to the app, or to
~/Finger Rehab Data when that folder cannot be written.

Neither is signed, so the first open needs one click through.
Windows: "Windows protected your PC", More info, Run anyway.
Mac: System Settings, Privacy & Security, Open Anyway, password.

To rebuild after changing the source, run build_app.sh (Mac) or
build_app.bat (Windows) from this folder. Each drops its files back
here and refreshes docs/lab_package, the folder that goes to the lab.
