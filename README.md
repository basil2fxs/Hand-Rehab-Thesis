# Finger Rehab

Finger rehab game for stroke patients. Python program runs on a laptop, Arduino on the hand rehab device. Built on top of Satoru Nakayama's 2025 software thesis. I kept his hardware protocol and FSR press-detection algorithm so the old patient data still loads.

## 2026 vs 2025

| What | 2025 version | This version |
|---|---|---|
| Modes | Classic only (fixed pattern) | Classic + Adaptive + Rhythm |
| Hands | Right only, 4 sensors | Left, right, or both. 4 or 8 sensors |
| Arduinos supported | 1 | 1 or 2 (one per hand for bilateral) |
| Finding the COM port | Edit the .py and hardcode it | Auto-detect by USB vendor ID, or pick in the Settings screen |
| Platforms | Windows only (hardcoded windib SDL driver) | Mac, Windows, Linux |
| Pause mid-block | Not supported | `P` key, freezes notes and audio |
| Data per session | trials.csv only | trials.csv + 200 Hz raw.csv + metadata.json with config snapshot |
| Atomic saves | No, a crash mid-save corrupts the file | Yes (write tmp, then rename) for metadata + calibration |
| Tests | None | 327 |
| Config | Hardcoded constants at the top of the .py | YAML default + a user override file the Settings screen writes to |
| Code shape | 1 file, ~2500 lines | ~30 files split into hardware / game / audio / data / ui / analytics |

### What each new mode does

Adaptive is the one I think actually scores points as research. It watches the patient's hit rate and reaction time per finger, then picks the next finger to stim and how fast to fire it. Target is 70 to 80 percent hit rate, the Guadagnoli and Lee challenge-point band where motor learning sits fastest. Weak fingers get picked more. Miss three in a row and the engine slows down hard and biases toward the patient's strongest finger so they get an easy win.

Rhythm plays a song, runs librosa to find the beats, then drops falling notes on those beats. The patient presses on the beat. Each press is scored Perfect, Great, Good, Late, Early or Miss in milliseconds from the beat.

Bilateral runs two Arduinos at once, one per hand. The host auto-detects both and assigns by plug order (first detected = right, second = left). You can override that in the Settings screen if it's the wrong way around. Each hand's sensors calibrate separately so a strong right and a weak left don't share thresholds.

## Quick start

```
pip install -r requirements.txt
python main.py
```

If no Arduino is plugged in, it falls back to keyboard mode.

## Keyboard fallback

| Hand mode | Keys |
|---|---|
| Right | `J K L ;` (index, middle, ring, little) |
| Left | `F D S A` (index, middle, ring, little, same finger order) |
| Both | `J K L ;` on the right + `F D S A` on the left. 8 keys total |

Index is always lane 0, little is always lane 3.

## Settings screen

Click the cog in the bottom-right of the title screen.

What's inside:

- Live FSR readout per finger so you can check each sensor is firing before the patient starts
- A panel listing the serial ports the host can see
- A cycle button per hand (LEFT / RIGHT) to pick which port handles that hand
- A `Test STIM` button per hand that fires STIM:1 through STIM:4 at 250 ms gaps so each motor pulses on its own
- A Refresh button to re-scan ports if you plug something in mid-test

Assignments save to `config/user_settings.yaml` and stick across restarts.

## Sessions

Every block writes a folder under `sessions/` (next to `main.py` from source, or next to the `.app` / `.exe` from a build):

```
sessions/
  sessions_index.csv                one line per block, the table of contents
                                    (leads with a date column for day filtering)
  <YYYY-MM-DD>/                     everything recorded that day, in one place
    <participant>_<HHMMSS>_<mode>/
      trials.csv       one row per trial, flushed after each row
      raw.csv          every FSR sample at 200 Hz, flushed every 50 ms
      metadata.json    participant, hand, software version, config snapshot,
                       block summary aggregates
      report.html      auto-generated researcher report, tables + charts
      summary.csv      the block summary flattened to one spreadsheet row
      charts/          the report's figures as standalone PNGs
```

A trial campaign across many patients and modes stays navigable: open a
date folder and every block from that day is there, sorted by
participant then time. Folders copied out of their day directory stay
traceable because metadata.json and trials.csv carry full timestamps.

The report, summary and charts generate automatically when a block ends (config key `report.enabled`). The `Data folder` button on the Results screen opens the session folder in Finder / Explorer.

`metadata.json` gets re-written every 10 trials so a hard kill still leaves a usable record. Saves write to a `.tmp` file then rename, so a crash mid-save doesn't blow away the prior snapshot.

If an Arduino unplugs mid-block, a `source_disconnected` event lands in `raw.csv` so you can see exactly when it dropped out.

## Building a standalone app

```
./build_app.sh        # macOS / Linux
build_app.bat         # Windows
```

The ready-to-run apps land in `builds/` at the project root (PyInstaller intermediates stay in `bin/`):

- Mac: `builds/Mac/Finger Rehab.app`
- Windows: `builds/Windows/Finger Rehab.exe` (one file)
- Linux: `builds/Linux/Finger Rehab` (one file)

The apps are fully self-contained: Python, pygame, numpy, librosa and matplotlib all ship inside. Nothing to install on the target machine, copy the app over and double-click. Session data writes to a `sessions/` folder next to the app. Each `builds/` subfolder carries a plain-text how-to.

PyInstaller only builds for the platform you're on. Cross-compile isn't a thing here. `.github/workflows/build-apps.yml` builds the Mac and Windows apps on GitHub runners instead: Actions tab, run `build-apps`, download the two zips.

First launch on a fresh machine: macOS Gatekeeper flags unsigned apps, so right-click the .app, Open, then Open again, once. After that it double-clicks normally. Windows SmartScreen has the same one-time "More info, Run anyway".

## Tests

```
python -m unittest discover -s tests
```

327 tests at the time of writing. They cover the scoring math, FSR detector edge cases, multi-Arduino routing, EEG marker protocol, atomic writes, headless pygame boot, pause and resume, source disconnection, and keyboard fallback for each hand.

## Folder layout

```
main.py                  start the game from source
build_app.sh / .bat      build the standalone app
finger_rehab.spec        PyInstaller config
Finger Rehab.command     double-click launcher for Mac

rehab/                   the app itself
  hardware/              FSR detector, serial sources, calibration profile
  game/                  engine, scheduling, classic/adaptive/rhythm/mirror
  audio/                 librosa wrapper + pygame.mixer wrapper
  data/                  CSV + JSON writers
  ui/                    screens + widgets
  analytics/             adaptive challenge-point algorithm
config/
  default.yaml           shipped defaults, heavily commented
  user_settings.yaml     what the Settings screen writes (gitignored)
  calibration/           measured press calibration, one file per hand
assets/                  music + images
analysis/
  session_analysis.ipynb the whole analysis, self-contained. No other
                         file needed: run the first cell, pick a save,
                         then Run All
  figures/               what the notebook draws, ready for the report
arduino/                 the firmware that is on the device now
  firmware_on_device/    PlatformIO project, this is what is flashed
  ADDRESS/               one-off sketch for setting a sensor's I2C address
tools/                   hardware check scripts, run from a terminal
tests/                   run these before trusting a change
builds/                  ready-to-run apps (Mac/ Windows/) + how-tos
sessions/                what the game records, one folder per block

bin/                     old stuff, nothing here is used by the game
  old_handover_sketch_Arduino_20251111/  superseded, see below
  old_interactive_game/    the 2025 rhythm game and its data
  example_session_data.zip example folder layout from the handover
```

## References

- FSR press-detection algorithm, CSV trial schema and stim event protocol come from Satoru Nakayama's 2025 software thesis (`Past/2025_Theses/Software - Satoru Nakayama .../rhythm_game_ver.FINAL.py`).
- The firmware on the device is `arduino/firmware_on_device/` (PlatformIO). It drives the motors on D11, D10, D9 and D6 for index to pinky, samples the four I2C sensors at 200 Hz, and speaks the same serial protocol as the older sketch: `FSR: a,b,c,d` out at 115200, `STIM:n` and `STOP` in.
- The earlier handover sketch is kept at `bin/old_handover_sketch_Arduino_20251111/` for reference only. It drove the motors on D3 to D6, which is why the buzzers never worked on this wiring: only the pinky pin overlapped. Everything else about the two is the same, including the 150 ms stim hold and the 200 Hz sample rate.
- On connect the firmware buzzes each of the four motors in turn as a self-test, which takes about 1.6 s. That is expected, not a fault. The host waits 3 s after opening the port so the boot finishes before it starts reading.
