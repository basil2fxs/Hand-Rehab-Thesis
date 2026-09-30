# Bundled avrdude

avrdude is the uploader the Arduino IDE uses. It ships inside the app so Settings, Setup, Flash firmware works on a
computer with no developer tools. It isn't kept in git; fetch it with:

```bash
python3 builds/fetch_avrdude.py                    # this system
python3 builds/fetch_avrdude.py --platform win32   # Windows
```

Each platform folder gets `avrdude` (or `avrdude.exe`), `avrdude.conf`, `LICENSE.txt` and `SOURCE.txt`.

## Licence

avrdude is GPL-2.0-or-later. `LICENSE.txt` is its licence text and `SOURCE.txt` names the matching source archive;
both travel with any copy of the app. The game runs avrdude as a separate program and uses none of its code, so the
game's own licence is unaffected.

## Apple silicon

The binary is x86_64, so it runs under Rosetta 2. macOS offers to install Rosetta the first time; the app says so if
flashing fails for that reason.
