<h1 align="center">Finger Rehab</h1>

<p align="center">
  Ten finger games that measure and train the hand, run from a laptop with an Arduino hand device.
</p>

<p align="center">
  <a href="https://github.com/basil2fxs/Hand-Rehab-Thesis/actions/workflows/build-apps.yml"><img alt="build" src="https://github.com/basil2fxs/Hand-Rehab-Thesis/actions/workflows/build-apps.yml/badge.svg"></a>
  <a href="tests"><img alt="tests" src="https://img.shields.io/badge/tests-pytest-4c1"></a>
  <img alt="platforms" src="https://img.shields.io/badge/platforms-macOS%20%7C%20Windows-lightgrey">
  <img alt="python" src="https://img.shields.io/badge/python-3.12%2B-blue">
</p>

![The hub, with all ten games](docs/images/hub.png)

## Quick start

```
pip install -r requirements.txt
python main.py
python -m pytest tests
```

Nothing plugged in? It falls back to the keyboard: `J K L ;` for the
right hand, `F D S A` for the left, index to little on both. Log in,
play a game, or press PLAY ALL to run the whole study battery in order.

Prebuilt apps: `./builds/build_app.sh` on macOS, `builds\build_app.bat`
on Windows, or download the zips from the Actions tab.

## The ten games

| Game | What it is |
| --- | --- |
| **Reaction** | Press the key that lights up, fast. Measures eye-to-hand speed. |
| **Adaptive** | Hit cued keys as the pace adapts to you. Keeps practice at the right challenge. |
| **Muscle Memory** | Record takes of a piano riff, session by session. Builds muscle memory. |
| **Chords** | Press 2-4 keys as one chord. Trains fingers to move together, and to stay still. |
| **Rhythm** | Press in time with a song. Practises movement timing to a beat. |
| **Syllables** | Catch the right part of the word as it falls. Builds the sound skills reading rests on. |
| **Mirror** | Same finger, both hands, pressed as one. Practises moving the hands together. |
| **Force Pilot** | Keep your press inside a moving corridor. Trains smooth force control. |
| **Buzz Hunt** | Feel which finger buzzed and press it. Measures and trains the sense of touch. |
| **Echo** | Watch the keys light up, then play them back in order. Measures memory span. |

Force Pilot and Buzz Hunt need the device. The other eight play on the
keyboard.

Muscle Memory can run a riff file: a YAML file naming the blocks, the
finger order, the pause after every press and the rests. Load one from
Settings (Riff file), by dragging it onto the window on a menu screen,
or by saving it into `config/pattern_sequences/` as `current.yaml`. It
then runs for every Muscle Memory game until you load another or press
Use built-in riff. Examples and the format live in
[docs/pattern_sequences](docs/pattern_sequences), and Settings writes a
commented template you can fill in.

## Hardware

One Arduino per hand, up to two hands, each board carrying four
SingleTact force sensors and four vibration motors (index to little).
The firmware in `arduino/firmware_on_device` samples the sensors at
200 Hz and drives the motors on D11 D10 D9 D6, speaking `FSR: a,b,c,d`
out and taking `STIM:n` and `STOP` in at 115200 baud. Presses are
reported in newtons off the 10 N sensor calibration, and logging in
runs a short per-finger calibration so the software knows what a light
press feels like for that person. The first board found is the right
hand and the second the left; Settings can pin a port to a hand
instead. On connect each motor buzzes once as a self-test, which is
normal.

Settings has two firmware buttons. Flash firmware writes the game
firmware to the board with a bundled avrdude, no developer tools
needed. Sensor address moves one SingleTact to a new I2C address, and
only ever with one sensor wired up: every board also answers 0x04, so a
change from 0x04 would re-address the lot. Details in
[docs/flashing.txt](docs/flashing.txt).

## Lab package

`docs/lab_package` is the one folder the EEG lab gets: the exe,
`eeg_lab.yaml`, `run_in_psychopy.py` and a `source/` copy of the game.
CI rebuilds it as `FingerRehab-EEGLab-Windows.zip` on every push; setup
notes are in `docs/eeg_lab_setup.txt`.

## Data and analysis

Every game writes `sessions/<date>/<participant>_<time>_<mode>/` with
`trials.csv` (one row per trial), `raw.csv` (every force sample),
`metadata.json` and a `report.html`. `sessions_index.csv` is the table
of contents.

`analysis/session_analysis.ipynb` is the whole analysis in one file.
Open it, run the first cell, pick a session, Run All. Figures and CSV
exports land inside the session folder they describe, so each folder
stands on its own. The cohort cells near the end read the whole tree
and write `sessions/cohort_results/`.

## Licence

Thesis work by Basil Toufexis, Curtin University, 2026. No licence file
yet, so ask before reusing the code. It is built on Satoru Nakayama's
2025 thesis software, whose serial protocol and press detection are
kept so the old patient data still loads.

Third-party assets carry their own terms: music by Kevin MacLeod under
CC BY 4.0 (`assets/music/ATTRIBUTION.md`), the hand icon from Google
Material Icons under Apache 2.0 (`assets/icons/LICENSE`), the syllable
word bank written for this project (`assets/words/LICENCE.txt`), and
avrdude 8.0-arduino.1 under GPL-2.0-or-later, run as a separate program
and shipped with its licence and a source pointer in
[tools/avrdude](tools/avrdude).
