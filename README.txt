# Finger Rehab

Finger rehab game for my thesis. Python on a laptop, Arduino on the
hand device (4 force sensors + 4 buzzers per hand, one or two hands).
Built on Satoru Nakayama's 2025 thesis software; his serial protocol
and press detection stayed so the old patient data still loads.

## Quick start

```
pip install -r requirements.txt
python main.py
```

No Arduino plugged in? It falls back to keyboard. Log in with a name
and age, pick a game, play. A session is as many games as you want;
data saves even if you quit a game halfway.

Two boards: the first one detected is the right hand, the second is
the left. The login screen and Settings both show which port went to
which hand. Settings can pin a port to a hand instead; a pinned port
that is no longer present is ignored and plug order takes over.

Keyboard keys: right hand `J K L ;`, left hand `F D S A` (index to
little on both). Both hands is all 8.

## The ten games

- Reaction: press as fast as you can after a random wait. Measures
  reaction time.
- Muscle Memory: repeating finger sequence you learn without noticing.
- Chords: 2 to 4 fingers together after a short single-finger warm-up.
  Measures how much force leaks into fingers that should stay still.
- Syllable Beats: tap the beats inside words, made for kids with
  dyslexia. Long words span both hands, left to right.
- Adaptive: watches your hit rate per finger and gives weak fingers
  more work at a pace you can just manage.
- Rhythm: falling notes on the beats of a song.
- Mirror: both hands press the same finger together.
- Force Pilot: your finger's pressure flies a craft through a
  corridor. Needs the sensors.
- Lighthouse: hold a gentle press steady, then keep it steady when
  the screen stops helping you. Needs the sensors.
- Buzz Hunt: a finger buzzes, you press the finger that felt it.
  Needs the buzzers.

First time on the sensors you get a quick calibration game (about 10 s
per hand) so the game learns what a light press is for each finger.

## Data

Every game writes a folder under `sessions/<date>/<participant>_<time>_<mode>/`:
`trials.csv` (one row per trial), `raw.csv` (every force sample at
200 Hz), `metadata.json` (config snapshot + block summary), plus an
auto report. `sessions_index.csv` is the table of contents.

## Analysis

`analysis/session_analysis.ipynb` is the whole analysis, one file.
Open it, run the first cell, pick a save, Run All. Figures and CSV
exports land inside the session folder they describe
(`sessions/.../analysis/`), so a session folder is self-contained.

## EEG lab

`EEG Lab.bat` / `EEG Lab.command` run the same game with markers
going to the lab's trigger box (`config/eeg_lab.yaml` is the whole
difference). The lab needs no install: CI builds
`FingerRehab-EEGLab-Windows.zip` on every push, one folder with the
exe, config and launcher inside. Setup notes in `docs/eeg_lab_setup.txt`.

## Standalone apps

```
./builds/build_app.sh        # macOS / Linux
builds\build_app.bat         # Windows
```

Apps land in `builds/`, fully self-contained, sessions write next to
the app. GitHub Actions builds Mac + Windows on every push (Actions
tab, download the zips). First launch: right-click Open on Mac,
"Run anyway" on Windows, once.

## Tests

```
python -m pytest tests
```

61 test files. Run them before trusting a change.

## Folder layout

```
main.py                  start from source
finger_rehab/            the app: hardware / game / audio / data / ui / analytics
config/                  default.yaml (commented), eeg_lab.yaml, calibration/
assets/                  music + images
analysis/                the notebook, nothing else
arduino/firmware_on_device/  what is flashed on the device (PlatformIO)
scripts/                 hardware check scripts (buzz soak, device test)
tests/                   the suite
docs/                    EEG setup, research notes, lab package files
builds/                  ready-to-run apps + the build scripts
sessions/                recorded data, one folder per game
bin/                     retired stuff, nothing in here is used
```

## Hardware notes

- Firmware drives motors on D11 D10 D9 D6 (index to pinky), samples
  the sensors at 200 Hz, speaks `FSR: a,b,c,d` out / `STIM:n`, `STOP`
  in at 115200.
- On connect it buzzes each motor once as a self-test (~1.6 s).
  That's normal. The host waits 3 s before reading.
- The old handover sketch lives in `bin/` for reference. It drove
  motors on D3 to D6, which is why buzzers never worked on this
  wiring until the pin map was fixed.
