# assets

Everything the game ships with apart from code. The whole folder goes into the exe, the Mac app and the lab folder's `source/`, and code finds a file here with `cfg.resolve_path("assets/...")`, which works the same from source and from a build.

| Folder | What is in it |
| --- | --- |
| `firmware/` | The board firmware Settings flashes: `finger_rehab_nano.hex`, the address tool `singletact_address_change.hex`, and `manifest.json` with a checksum for each (a hex that fails it is refused). Built from `arduino/` by `python3 builds/build_firmware.py` and by CI; not kept in git |
| [`icons/`](icons) | The app icon, and `pan_tool.png` (Google Material Icons, Apache 2.0, [LICENSE](icons/LICENSE)) for the hand buttons |
| [`music/`](music) | Songs for Rhythm and the menus, CC0 or CC-BY only, each with its `<song>.LICENCE.txt` and credited in [ATTRIBUTION.md](music/ATTRIBUTION.md). Rhythm won't start if there's no song here |
| [`charts/`](charts) | The study's Rhythm chart, frozen by `python3 scripts/build_study_chart.py` so every sitting hears the same notes |
| [`speech/`](speech) | Syllables audio, listed in `manifest.json`: a synthetic voice (Kokoro-82M, Apache 2.0) made by `scripts/syllables_tts.py`. `scripts/syllables_recording_kit.py` swaps in a recorded voice |
| [`words/`](words) | `syllables_source.txt`, the Syllables word list (band, then the word split into syllables with the stressed one in capitals, `A ba-NA-na`), and the JSON files the three `scripts/build_syllables_*.py` scripts make from it. Only rebuild the probe deliberately, because a changed probe starts a new series. Terms: [LICENCE.txt](words/LICENCE.txt) |
| [`srt/`](srt) | The lab SRT's four tones, copied unchanged from its PsychoPy script, one per square from left to right; `srt.tone_dir` and `srt.tone_files` in `config/default.yaml` point here |

To add a song, put the mp3 in `music/` beside its `<song>.LICENCE.txt` and give it a line in `ATTRIBUTION.md`. Only use CC0 or CC-BY music, since the repository is public.
