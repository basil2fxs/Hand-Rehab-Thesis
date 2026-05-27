# Finger Rehab

Finger rehab game for stroke patients. Python on a laptop, Arduino on the device driving force sensors and vibration motors. I built this on top of Satoru Nakayama's 2025 software thesis. I kept his hardware protocol and FSR press-detection algorithm so the old patient data still loads. The rest is mine.

## What's new vs the 2025 game

| What | 2025 game | This version |
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
sessions/<participant>_<YYYYMMDD_HHMMSS>/
  trials.csv       one row per trial, flushed after each row
  raw.csv          every FSR sample at 200 Hz, flushed every 50 ms
  metadata.json    participant, hand, software version, config snapshot,
                   block summary aggregates
```

`metadata.json` gets re-written every 10 trials so a hard kill still leaves a usable record. Saves write to a `.tmp` file then rename, so a crash mid-save doesn't blow away the prior snapshot.

If an Arduino unplugs mid-block, a `source_disconnected` event lands in `raw.csv` so you can see exactly when it dropped out.

## Building a standalone app

```
./build_app.sh        # macOS / Linux
build_app.bat         # Windows
```

Output lands in `bin/dist/`:

- Mac: `bin/dist/Finger Rehab.app`
- Windows: `bin/dist/Finger Rehab/Finger Rehab.exe`
- Linux: `bin/dist/Finger Rehab/Finger Rehab`

PyInstaller only builds for the platform you're on. Cross-compile isn't a thing here.

## Tests

```
python -m unittest discover -s tests
```

327 tests at the time of writing. They cover the scoring math, FSR detector edge cases, multi-Arduino routing, EEG marker protocol, atomic writes, headless pygame boot, pause and resume, source disconnection, and keyboard fallback for each hand.

## Folder layout

```
main.py                  entry point
config/
  default.yaml           shipped defaults
  user_settings.yaml     auto-written by the Settings screen (gitignored)
rehab/                   the Python app
  hardware/              FSR detector + serial sources
  game/                  engine + classic / adaptive / rhythm modes
  audio/                 librosa wrapper + pygame.mixer wrapper
  data/                  CSV + JSON writers
  ui/                    screens + widgets
  analytics/             adaptive challenge-point engine
assets/                  music + images
sessions/                generated per session
tests/                   327 tests
bin/                     stuff the game doesn't need at runtime
  arduino_firmware/      Aiden's PlatformIO project (the official build)
  build/ + dist/         PyInstaller output
```

## Credit

- FSR press-detection algorithm, CSV trial schema and stim event protocol come from Satoru Nakayama's 2025 software thesis (`Past/2025_Theses/Software - Satoru Nakayama .../rhythm_game_ver.FINAL.py`).
- The Arduino firmware in `bin/arduino_firmware/` is Aiden's hardware build (PlatformIO project with I2C sensors and a few modular C++ libs).
- Everything in `rehab/` is mine.
