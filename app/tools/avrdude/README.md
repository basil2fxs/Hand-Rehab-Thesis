# Bundled avrdude

avrdude, the Arduino IDE's uploader, ships inside the app so Settings, Setup, Flash firmware works on a computer with no developer tools. It is not kept in git; fetch it with:

```bash
python3 builds/fetch_avrdude.py                    # this system
python3 builds/fetch_avrdude.py --platform win32   # Windows
```

Each platform folder gets `avrdude` (or `avrdude.exe`), `avrdude.conf`, `LICENSE.txt` and `SOURCE.txt`.

avrdude is GPL-2.0-or-later. `LICENSE.txt` is its licence text and `SOURCE.txt` names the matching source archive; both travel with any copy of the app. The game runs avrdude as a separate program and uses none of its code, so the game's own licence is unaffected. On Apple silicon the x86_64 binary runs under Rosetta 2, which macOS offers to install the first time.
