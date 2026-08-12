Finger Rehab, ready-to-run apps
===============================

Mac/       Finger Rehab.app     double-click to play
Windows/   Finger Rehab.exe     double-click to play

Self-contained: Python and every library ship inside, nothing to
install. Session data goes to a sessions/ folder next to the app.

First launch shows a one-time security prompt because the app is not
signed. Mac: right-click, Open, Open again. Windows: More info, Run
anyway.

To rebuild after changing the source, run build_app.sh (Mac) or
build_app.bat (Windows) from this folder. Each drops its app back
here and refreshes docs/lab_package, the folder that goes to the lab.
