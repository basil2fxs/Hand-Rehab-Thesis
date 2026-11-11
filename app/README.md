# app

The game's code and everything it ships with: how to run it, change it, test it and release it. To install the game instead, see the [front page](../README.md).

| Path | What is in it |
| --- | --- |
| `main.py` | Starts the game: reads the flags and the config, finds the boards |
| [`finger_rehab/`](finger_rehab) | The code. Its README explains how the parts fit |
| [`config/`](config) | Every setting, commented, and the lab's overlay |
| [`assets/`](assets) | Firmware, icons, music, speech, word lists, the lab's tones |
| [`arduino/`](arduino) | The board firmware's source |
| [`docs/`](docs) | Study-day kit, research notes, the lab checklist, screenshots |
| [`scripts/`](scripts) | Tools run by hand: device checks, timing, simulation |
| [`tests/`](tests) | Over 4,000 tests, all headless |
| [`builds/`](builds), [`installers/`](installers), [`tools/`](tools) | Building the installers and the firmware, and the bundled avrdude |

## Run from source

```bash
git clone https://github.com/basil2fxs/Hand-Rehab-Thesis.git
cd Hand-Rehab-Thesis
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
python app/main.py
```

On Windows the venv lines are `py -3.12 -m venv .venv` and `.venv\Scripts\activate`. Without a board the keyboard can be used instead: `J K L ;` for the right hand, `F D S A` for the left. Recordings and `rehab.log` go to `app/sessions/`. On a Mac, `Local_Runner.command` runs the same code with a double-click and puts them in the top-level `sessions/`, where the notebook looks first.

| Flag | What it does |
| --- | --- |
| `--config config/eeg_lab.yaml` | Applies a second YAML file on top of the defaults, here the lab's markers |
| `--source keyboard` | Keyboard only. With `serial`, the game won't fall back to the keyboard |
| `--port PORT`, `--list-ports` | Skip the board search, or print what it sees and exit |
| `--hand`, `--mode`, `--participant` | Start with the hand, the game or the login name already set |
| `--data-dir DIR` | Where the session folders and the log go |
| `--windowed` | A window instead of full screen |
| `--eeg-port PORT`, `--no-eeg-box` | Point the lab build at a trigger box, or run it without one |
| `--eeg-simulator` | The EEG simulator window instead of the game |
| `--check-tools REPORT` | Check the flashing tools, write a JSON report and exit |

`--watch` and the two autostart flags are used by the auto-start watcher and the installer. A second copy of the game won't start, because on Windows the first copy is already using the board's port.

## Making a change

Most changes touch three places: the code, its setting in `config/default.yaml` with a comment on why it has that value, and a test that fails without the change.

- A setting: [config](config), which also gives the order the files are read in.
- A game: [finger_rehab/game/modes](finger_rehab/game/modes), with the steps and tests a new one needs.
- A screen: [finger_rehab/ui](finger_rehab/ui), then `python3 scripts/make_screenshots.py` for the pictures.
- What gets logged: [finger_rehab](finger_rehab) describes the session folder. The notebook keeps its own copy of the format, and `tests/test_notebook_matches_software.py` fails when the two disagree.
- The firmware: [arduino](arduino), then the wiring table in [hardware](../hardware), which `tests/test_hardware_docs.py` checks against it.

## Test

```bash
cd app
python -m pytest tests -q
```

It takes about five minutes. CI runs the same suite on every push but skips the real-time frame tests ([`tests/realtime.py`](tests/realtime.py)), so run the whole suite on a real machine before a release. [tests](tests) explains how the tests are grouped.

## Release

Push to `main`. The [build-apps](../.github/workflows/build-apps.yml) workflow runs the tests, builds `FingerRehab-Setup-Windows.exe`, `FingerRehab-macOS.dmg` and `FingerRehab-EEGLab.zip` from that commit, and publishes them as the release named after `SOFTWARE_VERSION` in `app/finger_rehab/data/session.py`. If that number hasn't changed, the new files replace the ones already on that release. For a new version, raise `SOFTWARE_VERSION` and the two matching strings in `app/finger_rehab.spec` (a test checks they agree). Every session's `metadata.json` records the version, so a result can be traced back to its build. For local builds, see [`builds/`](builds).

## Generated files

Rebuild these, from `app/`, after changing what they come from:

| File | Command |
| --- | --- |
| `EEG_Lab/source/`, `EEG_Lab/eeg_lab.yaml` | `python3 scripts/check_lab_sync.py --fix` |
| `docs/images/*.png` | `python3 scripts/make_screenshots.py` |
| `docs/images/eeg_*.svg` | `python3 scripts/make_eeg_cheat_sheet.py` |
| `docs/images/analysis_*.png` | `python3 scripts/simulate_cohort.py --out <folder>`, then the notebook on that folder |
| `assets/firmware/*.hex` | `python3 builds/build_firmware.py` (needs PlatformIO) |
| `tools/avrdude/` | `python3 builds/fetch_avrdude.py` |
| `assets/words/*.json` | `python3 scripts/build_syllables_bank.py`, `build_syllables_pools.py`, `build_syllables_probe.py` |
| `assets/charts/*.json` | `python3 scripts/build_study_chart.py` |

Tests fail when the cheat sheet or the lab folder is out of date. Nothing checks the screenshots, so remake them after changing a screen.

## Taking it further

What the thesis left open, and where each piece starts:

- **Patients.** Only healthy adults have played it. The fields a patient sitting needs (affected side, impairment score, hand size) are under `session` in `config/default.yaml`, `instructions.spoken` reads each game's instruction aloud, and `analysis/patient_hand_sim.py` runs the detector on weak, slow and shaking presses.
- **The pads on a bench.** `scripts/pad_bench.py --characterise` and `scripts/force_check.py` put known masses on each pad. Neither was run, so the newton figures rely on the manufacturer's calibration.
- **Lab timing.** The markers' wire timing is checked. The screen's delay (`scripts/latency_check.py --display` filmed at 240 fps, read by `scripts/clip_delay.py`) and the sound's (Settings, Setup, Audio delay) still need measuring once on the lab PC.
- **Buzz strength.** The firmware fixes motor strength at compile time and only understands `STIM:n` and `STOP`, so the game can lengthen a buzz but not strengthen it.
- **Two boards.** Mirror has only run on simulated boards (`analysis/mirror_sim.py`); the timing bench in [hardware](../hardware) has to be done before any real gap between the hands is reported.
- **Syllables with readers with dyslexia**, and sittings on the left-hand device with the uncalibrated pads, were both moved to future work ([FINAL TRIAL RESULTS](../FINAL%20TRIAL%20RESULTS)).

## House rules

- Recorded data never goes in git: `sessions/` is ignored, and so is everything in `FINAL TRIAL RESULTS/` except its README. Session folders have the login name in them, so names are replaced with codes before anything is shared.
- Plain ASCII, Australian spelling, and READMEs that describe the project rather than speak as a person; `tests/test_readme.py` checks both.
- Settings for one computer go in `config/user_settings.yaml`, which is ignored, never in `default.yaml`.
- After changing a study sitting, time it again: `python3 scripts/measure_battery.py --preset study_battery --repeats 8`.
