# Developer

Tools for setting up and rehearsing the lab session, and notes for anyone changing the lab folder. Keep this folder on the development PC. The lab doesn't need it, and the release's `FingerRehab-EEGLab.zip` doesn't include it.

| | |
| --- | --- |
| `EEG simulator.cmd` | Rehearse without the lab: a window acts as the trigger box on COM10 and the amplifier |
| `Get PsychoPy.cmd` | Downloads the Standalone PsychoPy installer (2026.2.4, about 530 MB) into `downloads/`, checks its SHA-256 against the release's, and runs it |
| `Check this PC.cmd` | Checks the game's flashing tools and the USB driver of any Arduino plugged in |

## A new PC

1. Put the latest `Finger Rehab.exe` in `EEG_Lab` (from `FingerRehab-EEGLab.zip` on the [release](https://github.com/basil2fxs/Hand-Rehab-Thesis/releases/latest)).
2. Run `Get PsychoPy.cmd` and install PsychoPy with its defaults.
3. Plug in the hand device and the trigger box, then run `Check this PC.cmd`. If a board has no driver, open the game and go to Settings, Setup, USB driver, Get the driver. A box that isn't on COM10 is found because it's the one USB port sending no force stream, and its port is saved into this folder's `eeg_lab.yaml`.
4. In the game: Settings, Setup, Audio delay, once.

## The simulator

Double-click `EEG simulator.cmd`, then start the game the same way as at the lab. With no box on COM10 the game finds the simulator and runs as if the box were plugged in, and the menu says it's a rehearsal. Each marker shows on the simulated EEG with its number and meaning. The EEG signal is made up, but the bytes and pulse widths are real. With a second screen the simulator opens on it, and with one screen Alt+Tab switches between the two.

Keys: Space pauses, Up and Down change the gain, Left and Right change the time span, S saves the markers to a CSV, Esc quits.

From source on any computer, in `app/`: `python3 main.py --eeg-simulator` in one terminal, `python3 main.py --config config/eeg_lab.yaml` in another. For a real COM10, install a virtual serial pair (com0com, COM10 to COM11) and start the simulator with `--sim-port COM11`. On a Mac with the real hand device, `app/scripts/virtual_trigger_box.py` acts as the box instead and checks every byte it received against the game's logs when the game closes.

## How the lab folder is made

The lab runs the same game as every other build, with `eeg_lab.yaml` applied on top of the defaults. Only three things in `EEG_Lab` are written by hand and kept in git: `README.md`, `run_in_psychopy.py` and this folder. The rest are build products that git ignores:

- `source/`: a fresh copy of the game (`finger_rehab/`, `main.py`, `requirements.txt`, the two config files, `assets/`), deleted and rebuilt every time so it can't go stale.
- `eeg_lab.yaml`: a copy of `app/config/eeg_lab.yaml`, which the exe loads from beside itself.
- `Finger Rehab.exe`: only a Windows build (`app/builds/build_app.bat`) or CI can make it, so take it from the same release as the installers.
- `sessions/eeg/` with a note saying ActiView's recordings go there.

`app/scripts/build_lab_package.py` assembles all of it, and `build_app.sh`, `build_app.bat` and the CI workflow all call that one script, so the local folder and the release zip always match. Files created by running the folder (`config/`, `python_packages/`) are kept, and anything else found at the top level fails the build rather than being deleted without warning. `python3 app/scripts/check_lab_sync.py` checks whether `source/` and the yaml match the app, and `--fix` rebuilds them. `Local_Runner.command` refreshes them on every start, and `app/tests/test_eeg_contract.py` fails when they're out of date.

`run_in_psychopy.py` chooses how to start the game. On Windows it starts the exe beside it, which has its own Python built in. Anywhere else it runs `source/` with PsychoPy's Python, after installing any packages PsychoPy is missing into `python_packages/` beside it. It sets `FINGER_REHAB_DATA_ROOT` so the recordings go into this folder's `sessions/` either way.

## How a marker is made

The marker codes are defined in one place, `CODES` in `app/finger_rehab/hardware/eeg_trigger.py`. Each event is a single byte:

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

On the wire each byte is held for `eeg.pulse_ms`, then the line goes back to 0 and stays there for `eeg.gap_ms`. Events that happen at the same moment are queued by priority (session and block starts first, then stimuli, responses, feedback), so a marker can arrive late but is never wrong. A stimulus byte goes out straight after the frame that draws the stimulus; a press byte follows within a frame of the sample that counted the press. After three failed writes the port is reopened once, and if that fails too the session carries on, logging every marker it could not send and marking the block EEG-degraded.

Every byte is also an `eeg` row in `raw.csv`, with the time of the event and the time it reached the wire. When an EEG block ends, `events.tsv`, `events.json` and `markers_codes.csv` are built from those rows, so the file and the wire record can't disagree. `events.tsv` moves each press back to its sample on the board's clock (`press_offset_ms`) and to where the push began (`onset_offset_ms`).

To change the map, add the new code to `CODES`, raise `CODES_VERSION` (every session records the version it was made with), redraw the cheat sheet with `python3 app/scripts/make_eeg_cheat_sheet.py` (`app/tests/test_eeg_cheat_sheet.py` fails until it's redrawn), update the code table in `app/docs/eeg_lab_setup.txt` and check that `app/tests/test_eeg_contract.py` passes.
