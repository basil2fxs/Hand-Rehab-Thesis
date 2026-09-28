# Working on Finger Rehab

From a fresh clone to a change that is tested, built and released. The [README](README.md) is for people using the device; this page is for people changing it.

## Set up once

```bash
git clone https://github.com/basil2fxs/Hand-Rehab-Thesis.git
cd Hand-Rehab-Thesis
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
python app/main.py
```

On Windows the two venv lines are `py -3.12 -m venv .venv` and `.venv\Scripts\activate`. No board? The keyboard stands in: `J K L ;` right hand, `F D S A` left. On a Mac, `Local_Runner.command` starts the game with a double-click and records into `sessions/`.

Python 3.12 is what CI builds with and has wheels for every package; 3.10 or newer runs the game.

## Find your way

| To change | Look in |
| --- | --- |
| A game | `app/finger_rehab/game/modes/<game>.py` (its docstring is the research case) and its screen in `app/finger_rehab/ui/` |
| A setting, or the study sittings | `app/config/default.yaml`, every key commented; the sittings are `protocol.presets` |
| The lab version | `app/config/eeg_lab.yaml`, laid over `default.yaml` |
| Login, sessions, Play all | `app/finger_rehab/game/engine.py`, `app/finger_rehab/game/battery.py`, `app/finger_rehab/data/` |
| Boards, presses, EEG markers | `app/finger_rehab/hardware/` (the marker map is `eeg_trigger.py`) |
| The board's firmware | `app/arduino/` |
| The thesis analysis | `analysis/session_analysis.ipynb` |
| A tool run by hand | `app/scripts/`, listed in its [README](app/scripts/README.md) |

More detail: the maps of [app](app/README.md) and [the package](app/finger_rehab/README.md).

## Test

```bash
cd app
python -m pytest tests -q
```

The whole suite runs headless in about five minutes. Every change comes with a test that fails without it. CI runs the same suite on every push and releases nothing while it fails. A few tests play real 60 Hz frames and time them to within one frame, which a shared CI runner cannot do, so CI skips those ([`app/tests/realtime.py`](app/tests/realtime.py)); run the whole suite on your own machine before a release. After changing a study sitting, time it again: `python3 scripts/measure_battery.py --preset study_battery --repeats 8`.

## Build and release

Push to `main`. The [build-apps](.github/workflows/build-apps.yml) workflow then:

1. runs the tests, and builds `FingerRehab-Setup-Windows.exe`, `FingerRehab-macOS.dmg` and `FingerRehab-EEGLab.zip` from the same commit;
2. when every part passes, publishes the three as the release named after `SOFTWARE_VERSION` in `app/finger_rehab/data/session.py`. The same number again replaces that release's files; a new number makes a new release.

To start a new version, raise `SOFTWARE_VERSION` and the two matching strings in `app/finger_rehab.spec` (a test checks they agree), then push. Every session records the number, so the data always says which build made it.

To build on your own machine instead: `app/builds/build_app.sh` on a Mac, or `app\builds\build_app.bat` on Windows with Inno Setup 6 for the installer. The files land in `app/builds/Mac/` or `app/builds/Windows/`.

## Generated files

Rebuild these after changing what they come from. Commands run from `app/`.

| File | Comes from | Command |
| --- | --- | --- |
| `EEG_Lab/source/`, `EEG_Lab/eeg_lab.yaml` | the app | `python3 scripts/check_lab_sync.py --fix` |
| `docs/images/*.png` | the game's screens | `python3 scripts/make_screenshots.py` |
| `docs/images/eeg_cheat_sheet_*.svg` | the marker map | `python3 scripts/make_eeg_cheat_sheet.py` |
| `assets/firmware/*.hex` | `arduino/` | `python3 builds/build_firmware.py` (needs PlatformIO) |

## Newer libraries

`pip install --upgrade -r app/requirements.txt`, run the tests, push. CI builds with Python 3.12, set in the workflow; move it on once every package in `app/requirements.txt` has wheels for the newer Python.

## House rules

- Recorded data never goes in git. `sessions/` is ignored, and so is everything in `FINAL TRIAL RESULTS/` except its READMEs.
- Plain ASCII in every document, Australian spelling. `app/tests/test_readme.py` checks the READMEs.
- Settings for one machine go in `app/config/user_settings.yaml`, which is ignored, never in `default.yaml`.
