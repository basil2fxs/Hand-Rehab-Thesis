# Developer

For setting up and rehearsing the lab session, and for whoever changes the lab folder. This folder stays on the development PC; the release's `FingerRehab-EEGLab.zip` leaves it out.

| | |
| --- | --- |
| `EEG simulator.cmd` | Rehearse without the lab: a window plays the trigger box on COM10 and the amplifier |
| `Get PsychoPy.cmd` | Downloads the Standalone PsychoPy installer (2026.2.4, about 530 MB) into `downloads/`, checks its SHA-256 against the release's, and runs it |
| `Check this PC.cmd` | Checks the game's flashing tools and the USB driver of any Arduino plugged in |

## A new PC

1. Put the latest `Finger Rehab.exe` in `EEG_Lab` (from `FingerRehab-EEGLab.zip` on the [release](https://github.com/basil2fxs/Hand-Rehab-Thesis/releases/latest)).
2. Run `Get PsychoPy.cmd` and install PsychoPy with its defaults.
3. Plug in the hand device and the trigger box, then run `Check this PC.cmd`. A board with no driver: in the game, Settings, Setup, USB driver, Get the driver.
4. In the game: Settings, Setup, Audio delay, once.

## The simulator

Double-click `EEG simulator.cmd`, then start the game as at the lab. With no box on COM10 it finds the simulator and runs as if the box were plugged in; the menu says it is a rehearsal. Each marker shows on the simulated EEG with its number and meaning: the EEG is made up, the bytes and pulse widths are real. A second screen gets the simulator; on one screen, switch with Alt+Tab.

Keys: Space pauses, Up and Down change the gain, Left and Right change the time span, S saves the markers to a CSV, Esc quits.

From source on any computer, in `app/`: `python3 main.py --eeg-simulator` in one terminal, `python3 main.py --config config/eeg_lab.yaml` in another. For a real COM10, install a virtual serial pair (com0com, COM10 to COM11) and start the simulator with `--sim-port COM11`. On a Mac with the real hand device, `app/scripts/virtual_trigger_box.py` plays the box instead and checks every byte it received against the game's logs when the game closes.

## How the lab folder is made

The lab runs the same game as every other build, with `eeg_lab.yaml` laid over the defaults. Only three things in `EEG_Lab` are written by hand and kept in git: `README.md`, `run_in_psychopy.py` and this folder. The rest are build products that git ignores:

- `source/`: a fresh copy of the game (`finger_rehab/`, `main.py`, `requirements.txt`, the two config files, `assets/`), deleted and rebuilt every time so it can't go stale.
- `eeg_lab.yaml`: a copy of `app/config/eeg_lab.yaml`, which the exe loads from beside itself.
- `Finger Rehab.exe`: only a Windows build (`app/builds/build_app.bat`) or CI can make it, so take it from the same release as the installers.
- `sessions/eeg/` with a note saying ActiView's recordings go there.

`app/scripts/build_lab_package.py` assembles all of it, and `build_app.sh`, `build_app.bat` and the CI workflow all call that one script, so the local folder and the release zip can't drift apart. What running the folder leaves beside it (`config/`, `python_packages/`) is kept, and anything else found at the top level fails the build instead of being deleted unseen. `python3 app/scripts/check_lab_sync.py` says whether `source/` and the yaml match the app, and `--fix` rebuilds them; `Local_Runner.command` refreshes them on every start, and `app/tests/test_eeg_contract.py` fails when they lag.

`run_in_psychopy.py` picks the route: on Windows it starts the exe beside it, which carries its own Python; anywhere else it starts `source/` under PsychoPy's Python, first installing what PsychoPy lacks into `python_packages/` beside it. It sets `FINGER_REHAB_DATA_ROOT` so the recordings land in this folder's `sessions/` whichever route runs.

## How a marker is made

The code map is `CODES` in `app/finger_rehab/hardware/eeg_trigger.py`, the one source of truth. Each event is a single byte:

| Codes | Meaning |
| --- | --- |
| 20 to 25 | Preparation: the GET READY card, a Reaction wait and catch trial, a Rhythm buzz sent ahead of the beat, Force Pilot's runs and section edges |
| 30 to 38 | A stimulus. 30 is the screen alone; add 1 for the tone, 2 for the buzz, 4 when the screen doesn't show the finger. 38 is a Buzz Hunt buzz |
| 40, 41 | Muscle Memory: a cue from the repeating sequence, or from a random probe |
| 50 to 53 | Syllables: a set of options, a returned word, the prompt buzz, a speed trial |
| 100, 110, 120 + finger | A press: right finger, wrong finger, too early. 130 is no press in time, 131 a press with no trial running |
| 140 to 142 | Feedback: hit, miss, neutral |
| 200 + game, 220 + game | A game starts or ends (`MODE_IDS`), 219 a game abandoned |
| 240 to 245 | The session starting and ending, a pause and its resume, a rest and its end |

On the wire each byte is held for `eeg.pulse_ms`, then the line goes back to 0 and stays there for `eeg.gap_ms`. Events that collide queue by priority (session and block starts first, then stimuli, responses, feedback), so a marker can arrive late but never wrong. A stimulus byte goes out straight after the frame that draws the stimulus; a press byte follows within a frame of the sample that crossed the press point. After three failed writes the port is reopened once, and if that fails too the session carries on, logging every marker it could not send and marking the block EEG-degraded.

Every byte is also an `eeg` row in `raw.csv`, with the time of the event and the time it reached the wire. When an EEG block ends, `events.tsv`, `events.json` and `markers_codes.csv` are built from those rows, so the file and the wire record can't disagree. `events.tsv` moves each press back to its sample on the board's clock (`press_offset_ms`) and to where the push began (`onset_offset_ms`).

Changing the map means a new code in `CODES`, a raised `CODES_VERSION` (every session records the version it was made under), the cheat sheet redrawn with `python3 app/scripts/make_eeg_cheat_sheet.py` (`app/tests/test_eeg_cheat_sheet.py` fails while it is stale), the code table in `app/docs/eeg_lab_setup.txt` brought into line, and `app/tests/test_eeg_contract.py` passing.
