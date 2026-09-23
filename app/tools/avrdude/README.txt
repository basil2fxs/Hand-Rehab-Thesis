Bundled avrdude
===============

avrdude is the uploader the Arduino IDE runs under the bonnet. Shipping
it inside the exe and the .app is what makes Settings -> Flash Arduino
firmware a single click on a clinic PC that has no developer tools
installed. Nothing here is committed; fetch it with:

    python3 builds/fetch_avrdude.py                    this OS
    python3 builds/fetch_avrdude.py --platform win32   the other one

Each platform folder gets avrdude (or avrdude.exe), avrdude.conf,
LICENSE.txt and SOURCE.txt.

Licence
-------
avrdude is GPL-2.0-or-later. LICENSE.txt in each folder is the licence
text from the package itself and SOURCE.txt names the upstream source
archive that corresponds to the binary. Both must travel with any copy
of the app that carries the binary. Finger Rehab spawns avrdude as a
separate process and links none of its code, which is the "mere
aggregation" case the licence describes, so the game's own licensing is
unaffected.

macOS note
----------
The published binary is x86_64. On Apple silicon it runs under Rosetta
2, which macOS offers to install the first time an Intel-only program
runs (or softwareupdate --install-rosetta from a terminal). The app
says so in plain words if the spawn fails for that reason.
