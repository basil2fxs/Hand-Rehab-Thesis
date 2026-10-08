# app

The game's code and everything it ships with. To install the game, see the [front page](../README.md).

| Folder | What is in it |
| --- | --- |
| [`finger_rehab/`](finger_rehab) | The code: engine, games, screens, boards, logging |
| [`config/`](config) | Settings, each one commented, and the lab's overlay |
| [`assets/`](assets) | Board firmware, icons, music, speech, word lists, the lab's tones |
| [`arduino/`](arduino) | The board firmware's source, and how to flash it |
| [`docs/`](docs) | Study-day kit, research notes, the lab checklist, screenshots |
| [`scripts/`](scripts) | Tools run by hand: device checks, timing, simulation |
| [`tests/`](tests) | Automated tests |
| [`builds/`](builds) | Build scripts for the installers, the firmware and avrdude |
| [`installers/`](installers) | The Windows installer script |
| [`tools/`](tools) | The bundled avrdude, fetched when building |

## Run from source

```bash
git clone https://github.com/basil2fxs/Hand-Rehab-Thesis.git
cd Hand-Rehab-Thesis
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
python app/main.py
```

On Windows the venv lines are `py -3.12 -m venv .venv` and `.venv\Scripts\activate`. No board: the keyboard stands in, `J K L ;` right hand and `F D S A` left. `--config config/eeg_lab.yaml` runs the lab's settings. On a Mac, `Local_Runner.command` starts the game with a double-click.

## Test

```bash
cd app
python -m pytest tests -q
```

Headless, about five minutes. Every change comes with a test that fails without it. CI runs the same suite on every push but skips the real-time frame tests ([`tests/realtime.py`](tests/realtime.py)), so run the whole suite locally before a release.

## Release

Push to `main`. The [build-apps](../.github/workflows/build-apps.yml) workflow runs the tests, builds `FingerRehab-Setup-Windows.exe`, `FingerRehab-macOS.dmg` and `FingerRehab-EEGLab.zip` from the same commit, and publishes them as the release named after `SOFTWARE_VERSION` in `app/finger_rehab/data/session.py`; the same number again replaces that release's files. For a new version, raise `SOFTWARE_VERSION` and the two matching strings in `app/finger_rehab.spec` (a test checks they agree). Local builds: [`builds/`](builds).

## Generated files

Rebuild these after changing what they come from, from `app/`:

| File | Command |
| --- | --- |
| `EEG_Lab/source/`, `EEG_Lab/eeg_lab.yaml` | `python3 scripts/check_lab_sync.py --fix` |
| `docs/images/*.png` | `python3 scripts/make_screenshots.py` |
| `docs/images/eeg_*.svg` | `python3 scripts/make_eeg_cheat_sheet.py` |
| `docs/images/analysis_*.png` | `python3 scripts/simulate_cohort.py --out <folder>`, then the notebook on that folder |
| `assets/firmware/*.hex` | `python3 builds/build_firmware.py` (needs PlatformIO) |

## House rules

- Recorded data never goes in git: `sessions/` is ignored, and so is everything in `FINAL TRIAL RESULTS/` but its README.
- Plain ASCII in every document, Australian spelling; `tests/test_readme.py` checks the READMEs.
- Settings for one machine go in `config/user_settings.yaml`, which is ignored, never in `default.yaml`.
- After changing a study sitting, time it again: `python3 scripts/measure_battery.py --preset study_battery --repeats 8`.
