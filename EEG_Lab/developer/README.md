# Developer

For setting up and rehearsing the lab session. This folder stays on the development PC; the release's `FingerRehab-EEGLab.zip` leaves it out.

| | |
| --- | --- |
| `EEG simulator.cmd` | Rehearse without the lab: a window plays the trigger box on COM10 and the amplifier |
| `Get PsychoPy.cmd` | Downloads the Standalone PsychoPy installer (2026.2.4, about 530 MB) into `downloads/` and runs it |
| `Check this PC.cmd` | Checks the game's flashing tools and the USB driver of any Arduino plugged in |

## A new PC

1. Put the latest `Finger Rehab.exe` in `EEG_Lab` (from `FingerRehab-EEGLab.zip` on the [release](https://github.com/basil2fxs/Hand-Rehab-Thesis/releases/latest)).
2. Run `Get PsychoPy.cmd` and install PsychoPy with its defaults.
3. Plug in the hand device and the trigger box, then run `Check this PC.cmd`. A board with no driver: in the game, Settings, Setup, USB driver, Get the driver.
4. In the game: Settings, Setup, Audio delay, once.

## The simulator

Double-click `EEG simulator.cmd`, then start the game as at the lab. With no box on COM10 it finds the simulator and runs as if the box were plugged in; the menu says it is a rehearsal. Each marker shows on the simulated EEG with its number and meaning: the EEG is made up, the bytes and pulse widths are real. A second screen gets the simulator; on one screen, switch with Alt+Tab.

Keys: Space pauses, Up and Down change the gain, Left and Right change the time span, S saves the markers to a CSV, Esc quits.

From source on any computer: `python3 main.py --eeg-simulator` in one terminal, `python3 main.py --config config/eeg_lab.yaml` in another. For a real COM10, install a virtual serial pair (com0com, COM10 to COM11) and start the simulator with `--sim-port COM11`.
