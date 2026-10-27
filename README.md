<p align="center"><img src="app/assets/icons/app_icon_256.png" width="96" alt="Finger Rehab icon"></p>
<h1 align="center">Finger Rehab</h1>
<p align="center">A hand device and a game for Windows and macOS that measure and train finger movement.<br>Four force pads, four vibration motors and an Arduino Nano. Ten games. Every press is logged with its time and force.</p>
<p align="center"><a href="https://github.com/basil2fxs/Hand-Rehab-Thesis/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/basil2fxs/Hand-Rehab-Thesis?label=release&color=16a34a"></a> <a href="https://github.com/basil2fxs/Hand-Rehab-Thesis/actions/workflows/build-apps.yml"><img alt="build-apps" src="https://github.com/basil2fxs/Hand-Rehab-Thesis/actions/workflows/build-apps.yml/badge.svg"></a></p>
<p align="center"><a href="#install">Install</a> &middot; <a href="#the-ten-games">Games</a> &middot; <a href="#troubleshooting">Troubleshooting</a> &middot; <a href="#data">Data</a> &middot; <a href="#the-lab-folder">Lab folder</a> &middot; <a href="app/README.md">Working on the code</a></p>
<p align="center"><img src="app/docs/images/hub.png" width="88%" alt="The hub, where each game is picked"></p>

## Where things are

```text
Hand-Rehab-Thesis/
|
|-- Installers/               The Windows and macOS installers, from the latest release
|
|-- EEG_Lab/                  The folder that goes on the EEG lab computer
|   `-- developer/            Stays off the lab PC: the EEG simulator and set-up tools
|
|-- FINAL TRIAL RESULTS/      The study: what to run, and where each result goes
|
|-- analysis/                 The notebook and scripts that turn sessions into results
|
|-- app/                      The game
|   |-- main.py               Starts it
|   |-- finger_rehab/         The code: games, screens, boards, data logging
|   |-- config/               Settings files (eeg_lab.yaml turns on the lab's markers)
|   |-- assets/               Board firmware, icons, music, speech and word lists
|   |-- arduino/              Source code of the board firmware
|   |-- docs/                 Study-day forms, research notes, screenshots
|   |-- scripts/              Tools run by hand: device checks, simulations, lab sync
|   |-- tests/                Automated tests
|   `-- builds/               Scripts that build the installers
|
|-- hardware/                 Build the device: parts, wiring, pins, CAD and print files
|-- archive/                  Old material. Nothing here runs
|-- sessions/                 Recorded data (kept off GitHub)
`-- Local_Runner.command      Runs the game straight from the code on a Mac
```

Most folders carry a README that goes further. To change the software, start with [app/README.md](app/README.md) (run, test, release), then [app/finger_rehab](app/finger_rehab) for how the parts fit and what a session folder holds, and [app/finger_rehab/game/modes](app/finger_rehab/game/modes) to add or change a game. Results are made in [analysis](analysis) and filed in [FINAL TRIAL RESULTS](FINAL%20TRIAL%20RESULTS). The device itself is in [hardware](hardware) and [app/arduino](app/arduino).

## How it works

<p align="center"><img src="app/docs/images/device.jpg" width="46%" alt="The hand device: a drawing of the board and pads, and three photos of the build"><br><sub>The device. Parts are numbered in <a href="app/arduino">app/arduino</a>.</sub></p>

```mermaid
flowchart LR
  H["Fingers on four pads"] --> S["SingleTact 10 N sensors<br>I2C 0x05 to 0x08"]
  S --> A["Arduino Nano<br>200 Hz"]
  A -->|"FSR: a,b,c,d"| G["The game"]
  G -->|"STIM:n"| A
  A --> M["Four vibration motors"]
  G --> F["sessions/<br>trials.csv, raw.csv, metadata.json"]
  F --> N["analysis/session_analysis.ipynb"]
```

The Nano reads the four pads 200 times a second and sends each reading over USB as a line of text. The game turns those numbers into presses, picks the next finger to cue and sends `STIM:n` back to buzz finger n. Every sample it receives and everything it does goes into a session folder, and the notebook reads the folders.

There's no switch under a finger. Each pad keeps a slow baseline, and a press counts when the force crosses a trigger 30% of the way from that person's resting level to their light press, both measured at login. That is what lets a weak finger register: one fixed threshold had a little finger resting on its pad firing presses by itself. Settings, Setup, Press point moves the 30%.

<p align="center"><img src="app/docs/images/login.png" width="32%" alt="The login screen"> <img src="app/docs/images/hand.png" width="32%" alt="The hand choice screen"> <img src="app/docs/images/calibration.png" width="32%" alt="The quick calibration"><br><sub>Log in (free play, or a timed session of 15 to 60 minutes), pick the hand, calibrate. The game menu has the same session picker.</sub></p>

## Timing and limits

- **Sensing:** each pad reads 0 to 10 N in 512 steps, about 20 mN a step. The Nano reads all four every 5 ms (199 Hz measured) and sends them over USB in bursts, so a sample arrives about 10 ms late, up to 20 ms; the notebook can re-time presses on the board's own clock.
- **Presses:** a press counts when the smoothed force crosses the trigger. On the four sequence-task sessions of October 2026 the median press was counted one or two samples (5 to 10 ms) after the raw force crossed it, and a slow push is counted later (`analysis/count_lag.py`, `analysis/detector_lag_vs_rise.py`).
- **Screen and sound:** a cue shows on the next 60 Hz frame, up to 17 ms later. On the study computer a sound was heard 77 to 87 ms after the game played it and a buzz felt 74 ms after its command; measure each computer with Settings, Setup, Audio delay.
- **EEG markers:** a stimulus byte goes out on the frame that draws the stimulus, a press byte up to one frame after its sample, and `events.tsv` moves each press back to its sample and to where the push began. Checklist: [app/docs/eeg_lab_setup.txt](app/docs/eeg_lab_setup.txt).

## Install

- **Windows:** run [`FingerRehab-Setup-Windows.exe`](https://github.com/basil2fxs/Hand-Rehab-Thesis/releases/latest/download/FingerRehab-Setup-Windows.exe). No administrator needed. SmartScreen says "Windows protected your PC": More info, Run anyway.
- **macOS:** open [`FingerRehab-macOS.dmg`](https://github.com/basil2fxs/Hand-Rehab-Thesis/releases/latest/download/FingerRehab-macOS.dmg), drag Finger Rehab to Applications. First open: System Settings, Privacy & Security, Open Anyway.

Neither installer is signed, which is why each asks once. Both are on the [latest release](https://github.com/basil2fxs/Hand-Rehab-Thesis/releases/latest), built and tested from the same commit. From source: [app/README.md](app/README.md). No board? The keyboard stands in: `J K L ;` right hand, `F D S A` left.

## When a board is plugged in

The game opens within a second: a watcher installed at first launch checks the ports once a second. A board already plugged in when the computer started needs unplugging and plugging back in. A copy run from source or straight off the disk image never installs the watcher, and nor does the lab build. With the game open, a board plugged in at the login, on the hub or in Settings connects by itself; one that arrives mid-game waits for that game to end.

## The ten games

<table>
<tr>
<td align="center" width="33%"><img src="app/docs/images/reaction.png" alt="Reaction"><br><sub><b>Reaction</b></sub></td>
<td align="center" width="33%"><img src="app/docs/images/adaptive.png" alt="Adaptive"><br><sub><b>Adaptive</b></sub></td>
<td align="center" width="33%"><img src="app/docs/images/muscle_memory.png" alt="Muscle Memory"><br><sub><b>Muscle Memory</b></sub></td>
</tr>
<tr>
<td align="center" width="33%"><img src="app/docs/images/chords.png" alt="Chords"><br><sub><b>Chords</b></sub></td>
<td align="center" width="33%"><img src="app/docs/images/rhythm.png" alt="Rhythm"><br><sub><b>Rhythm</b></sub></td>
<td align="center" width="33%"><img src="app/docs/images/syllables.png" alt="Syllables"><br><sub><b>Syllables</b></sub></td>
</tr>
<tr>
<td align="center" width="33%"><img src="app/docs/images/mirror.png" alt="Mirror"><br><sub><b>Mirror</b></sub></td>
<td align="center" width="33%"><img src="app/docs/images/force_pilot.png" alt="Force Pilot"><br><sub><b>Force Pilot</b></sub></td>
<td align="center" width="33%"><img src="app/docs/images/buzz_hunt.png" alt="Buzz Hunt"><br><sub><b>Buzz Hunt</b></sub></td>
</tr>
<tr>
<td align="center" width="33%"><img src="app/docs/images/echo.png" alt="Echo"><br><sub><b>Echo</b></sub></td>
<td align="center" width="33%"><img src="app/docs/images/results.png" alt="Results"><br><sub><b>Results</b>, after every game</sub></td>
<td align="center" width="33%"></td>
</tr>
</table>

| Game | What the player does, and what it measures |
| --- | --- |
| **Reaction** | The lab's sequence task: press the finger whose card lights up. Sequence learning. |
| **Adaptive** | Press the finger whose lane lights up, at a pace that follows the player. Speed at a held difficulty. |
| **Muscle Memory** | Play a piano riff, take after take. Learning of a repeated sequence. |
| **Chords** | Press two to four fingers at once. Moving fingers together, holding the rest still. |
| **Rhythm** | Press on the beat of a song. Timing error against the beat. |
| **Syllables** | Catch the right part of a spoken word. Reading by sound. |
| **Mirror** | Press the same finger on both hands at once. How well the hands stay together. |
| **Force Pilot** | Keep a press on a moving line. Steady control of force. |
| **Buzz Hunt** | Feel which finger buzzed, then press it. The sense of touch. |
| **Echo** | Watch a sequence light up, then repeat it back. Memory span. |

Each game's file opens with the research behind it, and its settings sit under its key in `app/config/default.yaml` (Muscle Memory is `pattern`, the Reaction card `srt`). How a game is put together, and how to add one: [app/finger_rehab/game/modes](app/finger_rehab/game/modes).

## Settings

<p align="center"><img src="app/docs/images/settings.png" width="72%" alt="The Settings screen"></p>

The cog on the login screen. Four tabs: Hand device (the finger test, which board is which hand, a test buzz), Sound and cues (levels and cue switches), Setup, and Data (the data folder, the Muscle Memory riff, Test Mode). The Setup jobs (flashing notes: [app/arduino](app/arduino)):

- **Auto-start:** opens the game when the board is plugged in. The switch reads on or off, and off stays off.
- **Flash firmware:** writes the game firmware to the board with the avrdude bundled in the app, about ten seconds.
- **Sensor address:** moves one SingleTact to a new I2C address, with only that sensor connected.
- **Audio delay:** once per computer, times its sound and buzz with the microphone so Rhythm lands on the beat. About two minutes in a quiet room, board plugged in; on Windows it asks for taps on the index pad.

On Windows, Setup also has USB driver: it gets a board's missing driver from Windows Update. Whatever the screen changes is saved to `config/user_settings.yaml` beside the app and laid over `default.yaml`, which holds every setting with the reason for its value. How the files stack: [app/config](app/config).

## Troubleshooting

**A sensor reads nothing, or sits at zero.** A failed read is sent as 0, so a loose lead, a dead pad and a pad on the wrong address look the same. Reseat both ends of the lead, then Settings, Setup, Sensor address, Scan shows which addresses answer.

**A sensor drifts, or reads high at rest.** A pad squashed by the strap eats the gap between resting and pressing, and under 20 counts of travel is refused. Reposition the pad flat and calibrate again.

**The board is not found, or the port keeps changing.** The first board found is the right hand, the second the left. To pin one: Settings, Hand device, pick the port per hand, Save. A saved port that no longer exists falls back to plug order. On Windows, a board that never shows up at all usually has no driver yet: Settings, Setup, USB driver.

**Calibration is asked for every time.** Once per hand per session is the design. A repeat inside one session means the profile was refused: under 20 counts of travel, a trigger too high, or a pad reading zero when empty.

**A buzzer does not buzz.** Settings, Hand device, Test buzz fires that hand's motors in order, and clicking a finger tile buzzes just that finger. None firing on a board that streams fine is wiring, not software. No buzz before a cue means the cue is switched off in Sound and cues.

**Presses register on the wrong finger.** Two pads answer the same I2C address. Settings, Setup, Sensor address, with only that sensor connected: 0x05 index, 0x06 middle, 0x07 ring, 0x08 pinky. Never move a sensor off 0x04 with the others wired in.

**The game does not open when the board is plugged in.** Settings, Hand device, Refresh. If the board isn't listed, it's the lead or the driver (Setup, USB driver). If it is, Auto-start should read on; it only fires when a board arrives, so unplug and replug.

**The board needs re-flashing.** Settings, Setup, Flash firmware writes `app/assets/firmware/finger_rehab_nano.hex` with the bundled avrdude. A Nano runs one of two bootloaders; the app tries both and remembers which worked.

**The game runs but no data lands.** Settings, Data, Open data folder opens the folder in use, which is `~/Finger Rehab Data` when the app can't write beside itself. Check Test Mode is off (`game.test_mode_enabled`): it caps every block at six trials.

**The EEG box does not appear.** Markers are off in the shipped game; `app/config/eeg_lab.yaml` turns them on, loaded from beside the lab exe or with `--config config/eeg_lab.yaml` from source. Set `eeg.port` to the box's port. `eeg.require_port` true refuses to start without a box; false logs the markers only. `eeg.baud` stays 9600: 1200 would reset the box, so the game refuses it.

**Sessions look empty in the notebook.** It walks for `trials.csv` from the first `sessions` folder beside it or up to four levels above; a notebook copied elsewhere needs `SESSIONS_DIR` set in the Setup cell.

## Data

Each game is one folder, `sessions/<date>/<login>_<time>_<game>/`, and nothing is overwritten: a second folder with the same name gets `_1` on the end.

- `trials.csv`: one row per trial, with the finger cued, the reaction time, the peak force in newtons and the cue switches in force.
- `raw.csv`: every 200 Hz sample, with the presses, releases, cues and EEG markers as event rows on the same clock.
- `metadata.json`: the block summary, the calibration the block ran under, a copy of the config and the software version.
- `report.html`, `summary.csv` and `charts/` for a quick look, and for EEG blocks `events.tsv` and `markers_codes.csv`.

The folder name carries the login, so run `app/scripts/deidentify_sessions.py` before a copy leaves the computer. To analyse, open [`analysis/session_analysis.ipynb`](analysis), run the Setup cell, pick a save, Run All. Every column, and how the files are written: [app/finger_rehab](app/finger_rehab).

## The lab folder

`EEG_Lab` (the `FingerRehab-EEGLab.zip` of the same build) holds the exe, `eeg_lab.yaml`, `run_in_psychopy.py`, `README.md`, a `source/` copy and `sessions/`, where `sessions/eeg/` takes ActiView's recording under the name the game menu shows, copied in from the EEG PC when ActiView runs there. Its `developer/` folder stays on the development PC: an EEG simulator for rehearsing, the PsychoPy download and a new-PC check.
Open `run_in_psychopy.py` in PsychoPy Coder and press Run. Every other build has the markers switched off.
`python3 app/scripts/check_lab_sync.py` says whether the lab folder is the same game as the app; `--fix` makes it so, and `Local_Runner.command` does that on every start.
What each number means, in one picture: [EEG_Lab/README.md](EEG_Lab/README.md). How the folder is built and how the markers are made: [EEG_Lab/developer](EEG_Lab/developer). Checklist and code table: [app/docs/eeg_lab_setup.txt](app/docs/eeg_lab_setup.txt).

## Licence

Thesis work by Basil Toufexis, Curtin University, 2026; ask before reusing the code. It builds on Satoru Nakayama's 2025 software, whose serial protocol and press detection are kept so the old patient data still loads. Third-party terms live with the files: [music](app/assets/music/ATTRIBUTION.md), [icons](app/assets/icons/LICENSE), [words](app/assets/words/LICENCE.txt), [avrdude](app/tools/avrdude).
