# assets

Everything the game ships besides code.

| Folder | What is in it |
| --- | --- |
| `firmware/` | The board firmware Settings flashes: `finger_rehab_nano.hex`, the sensor address tool `singletact_address_change.hex` and `manifest.json` (a checksum for each). Built from `arduino/` by `python3 builds/build_firmware.py`, and by CI on every push; not kept in git. A hex that fails its checksum is refused |
| [`icons/`](icons) | `app_icon.icns` and `app_icon.ico`, the app icon. `pan_tool.png` (Google Material Icons open palm, Apache 2.0, [LICENSE](icons/LICENSE)) draws the hand buttons and badges |
| [`music/`](music) | Songs for Rhythm and the menus, CC0 or CC-BY only, each with its `<song>.LICENCE.txt`; credits in [ATTRIBUTION.md](music/ATTRIBUTION.md). With no song here Rhythm will not start: add one and press Rescan |
| [`speech/`](speech) | Syllables audio: `<word>.wav`, `chunks/<chunk>.wav` and `syllables/<word>_<k>.wav`, listed in `manifest.json`. Synthetic voice Kokoro-82M (Apache 2.0), voice bf_emma, made by `scripts/syllables_tts.py` and tidied by `scripts/syllables_recording_kit.py tidy` (2 October 2026). A recorded voice replaces it with the same kit: `list`, `cut`, `check` |
| [`words/`](words) | `syllables_source.txt`, the Syllables word list: the band (A, B or C), then the word split by hyphens with the stressed syllable in capitals (`A ba-NA-na`). `scripts/build_syllables_bank.py`, `build_syllables_pools.py` and `build_syllables_probe.py` write the JSON files the game reads. Rebuild the probe only on purpose: a changed probe starts a new series. Terms: [LICENCE.txt](words/LICENCE.txt) |
| [`srt/`](srt) | The lab SRT's four tones, copied unchanged from its PsychoPy script: `V.wav`, `B.wav`, `N.wav`, `M.wav`, one per square from left to right. About 660, 700, 790 and 890 Hz (E5 to A5), 200 ms files, audible for 115 to 130 ms; N and M are 10 to 12 dB quieter than V and B. `srt.tone_dir` and `srt.tone_files` in `config/default.yaml` point here |
