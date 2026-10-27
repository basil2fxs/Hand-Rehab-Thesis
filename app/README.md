# app

The game's code and everything it ships with. This page is the working loop for someone new to it: run it, change it, test it, release it. To install the game instead, see the [front page](../README.md).

| Path | What is in it |
| --- | --- |
| `main.py` | The entry point: reads the command line and the config, finds the boards, starts the engine |
| [`finger_rehab/`](finger_rehab) | The code: engine, games, screens, boards, logging. Its README explains how the parts fit |
| [`config/`](config) | Every setting, each one commented, and the lab's overlay |
| [`assets/`](assets) | Board firmware, icons, music, speech, word lists, the lab's tones |
| [`arduino/`](arduino) | The board firmware's source, and how to flash it |
| [`docs/`](docs) | Study-day kit, research notes, the lab checklist, screenshots |
| [`scripts/`](scripts) | Tools run by hand: device checks, timing, simulation, the lab folder |
| [`tests/`](tests) | The automated tests, over 4,000 of them, all headless |
| [`builds/`](builds) | Build scripts for the installers, the firmware and avrdude |
| [`installers/`](installers) | The Windows installer script (Inno Setup) |
| [`tools/`](tools) | The bundled avrdude, fetched when building |
| `requirements.txt` | What the game, the tests and the notebook need |
| `finger_rehab.spec` | The PyInstaller recipe for the exe and the Mac app |

## Run from source

```bash
git clone https://github.com/basil2fxs/Hand-Rehab-Thesis.git
cd Hand-Rehab-Thesis
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
python app/main.py
```

On Windows the venv lines are `py -3.12 -m venv .venv` and `.venv\Scripts\activate`. Python 3.12 is what CI builds with; `Local_Runner.command` (a double-click on a Mac) uses 3.14, so either works. No board: the keyboard stands in, `J K L ;` right hand and `F D S A` left. From source the recordings and `rehab.log` go to `app/sessions/`, while `Local_Runner.command` sends them to the top-level `sessions/`, where the notebook looks first.

The flags worth knowing, all in `main.py`:

| Flag | What it does |
| --- | --- |
| `--config config/eeg_lab.yaml` | Lays a second YAML over the defaults, here the lab's markers |
| `--source keyboard` | No boards at all; `serial` refuses to fall back to the keyboard |
| `--port PORT`, `--list-ports` | Skip the board search, or print what the search sees and exit |
| `--hand`, `--mode`, `--participant` | Start with the hand, the hub's game or the login name already set |
| `--data-dir DIR` | Where the session folders and the log go |
| `--windowed` | A window instead of full screen |
| `--eeg-port PORT`, `--no-eeg-box` | Point the lab build at a trigger box, or let it run without one |
| `--eeg-simulator` | Open the EEG simulator window instead of the game |
| `--check-tools REPORT` | Check the flashing tools, write a JSON report and exit (CI runs it) |

`--watch`, `--register-autostart` and `--unregister-autostart` belong to the auto-start watcher and the installer. A second copy of the game refuses to start (exit code 7), because on Windows the first copy holds the board's port.

## Making a change

Most changes touch three places: the code, its setting in `config/default.yaml` with a comment saying why it has that value, and a test that fails without the change. Where to start:

- A setting: [config](config), which also explains the order the files are read in.
- A game, or a new one: [finger_rehab/game/modes](finger_rehab/game/modes), with the steps and the tests a new game needs.
- A screen: [finger_rehab/ui](finger_rehab/ui), then `python3 scripts/make_screenshots.py` so the READMEs show it.
- What gets logged: [finger_rehab](finger_rehab) describes the session folder. The notebook carries its own copy of the format, and `tests/test_notebook_matches_software.py` fails when the two disagree.
- The firmware: [arduino](arduino), then the wiring table in [hardware](../hardware), which `tests/test_hardware_docs.py` checks against the firmware.

## Test

```bash
cd app
python -m pytest tests -q
```

Headless, about five minutes. Every change comes with a test that fails without it. CI runs the same suite on every push but skips the real-time frame tests ([`tests/realtime.py`](tests/realtime.py)), so run the whole suite locally before a release. How the tests are grouped: [tests](tests).

## Release

Push to `main`. The [build-apps](../.github/workflows/build-apps.yml) workflow runs the tests, builds `FingerRehab-Setup-Windows.exe`, `FingerRehab-macOS.dmg` and `FingerRehab-EEGLab.zip` from the same commit, and publishes them as the release named after `SOFTWARE_VERSION` in `app/finger_rehab/data/session.py`; the same number again replaces that release's files. For a new version, raise `SOFTWARE_VERSION` and the two matching strings in `app/finger_rehab.spec` (a test checks they agree). The version is also written into every session's `metadata.json`, so a result can always be traced to the build that made it. Local builds: [`builds/`](builds).

## Generated files

Rebuild these after changing what they come from, from `app/`:

| File | Command |
| --- | --- |
| `EEG_Lab/source/`, `EEG_Lab/eeg_lab.yaml` | `python3 scripts/check_lab_sync.py --fix` |
| `docs/images/*.png` | `python3 scripts/make_screenshots.py` |
| `docs/images/eeg_*.svg` | `python3 scripts/make_eeg_cheat_sheet.py` |
| `docs/images/analysis_*.png` | `python3 scripts/simulate_cohort.py --out <folder>`, then the notebook on that folder |
| `assets/firmware/*.hex` | `python3 builds/build_firmware.py` (needs PlatformIO) |
| `tools/avrdude/` | `python3 builds/fetch_avrdude.py` |
| `assets/words/*.json` | `python3 scripts/build_syllables_bank.py`, `build_syllables_pools.py`, `build_syllables_probe.py` |
| `assets/charts/*.json` | `python3 scripts/build_study_chart.py` (the study's frozen Rhythm chart) |

The cheat sheet and the lab folder have tests that fail when they fall behind. The screenshots don't, so shoot them again after changing a screen.

## Taking it further

What the thesis left open, and where each piece would start:

- **Patients.** The software was checked on healthy adults. The fields a patient sitting needs (affected side, impairment score, hand size) are already in `config/default.yaml` under `session` and land in `metadata.json`, and the notebook has an affected-against-unaffected chapter.
- **The pads on a bench.** `scripts/pad_bench.py --characterise` and `scripts/force_check.py` put known masses on each pad. Neither was run for the thesis, so the newton figures rest on the maker's calibration.
- **Screen and sound timing in the lab.** The wire timing of the markers is checked; the monitor's and the speaker's delays need a light sensor and a microphone once per lab PC (the Validate step in `docs/eeg_lab_setup.txt`).
- **Buzz strength.** The firmware fixes motor strength at compile time and only understands `STIM:n` and `STOP`, so the game can lengthen a buzz but not make it stronger. A firmware command for strength would make it a setting.
- **Two boards.** Mirror needs both, and its timing bench (in [hardware](../hardware)) has to come before any gap between the hands is reported.
- **Syllables with readers with dyslexia**, and sittings on the left-hand device with the uncalibrated pads: both planned, both moved to future work ([FINAL TRIAL RESULTS](../FINAL%20TRIAL%20RESULTS)).

## House rules

- Recorded data never goes in git: `sessions/` is ignored, and so is everything in `FINAL TRIAL RESULTS/` but its README. Session folders carry the login name, so names get replaced by codes before any analysis that is shared.
- Plain ASCII in every document, Australian spelling, and READMEs that describe the project rather than speak as a person; `tests/test_readme.py` checks both.
- Settings for one machine go in `config/user_settings.yaml`, which is ignored, never in `default.yaml`.
- After changing a study sitting, time it again: `python3 scripts/measure_battery.py --preset study_battery --repeats 8`.
