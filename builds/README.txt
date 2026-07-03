Finger Rehab, ready-to-run apps
===============================

Mac/       Finger Rehab.app        double-click to play
Windows/   Finger Rehab.exe        double-click to play

Both apps are fully self-contained. Python, pygame, numpy, librosa and
matplotlib all ship inside. Nothing needs installing on the target
machine: copy the app for your platform onto the PC and double-click.

Session data (trials, raw sensor CSVs, reports) is written to a
sessions/ folder created next to the app.

First launch on a new machine shows a one-time security prompt because
the app is not code-signed:
  Mac:      right-click the app, Open, then Open again. Once.
  Windows:  click "More info", then "Run anyway". Once.
After that it double-clicks normally.

To rebuild after changing the source: run build_app.sh on a Mac or
build_app.bat on a Windows PC (both sit in the project root). Each
drops its finished app back into this folder.
