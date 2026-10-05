# Developer

Tools for setting up and rehearsing the lab session. This folder stays on the development PC and does not go to the lab (the release's `FingerRehab-EEGLab.zip` leaves it out).

| | |
| --- | --- |
| `EEG simulator.cmd` | Rehearse the lab without the lab: a window plays the trigger box on COM10 and the amplifier |
| `Get PsychoPy.cmd` | Downloads the Standalone PsychoPy installer (2026.2.4, about 530 MB) into `downloads/` and runs it |
| `Check this PC.cmd` | Checks the game's flashing tools and the USB driver of any Arduino plugged in |

## A new PC

1. Put the latest `Finger Rehab.exe` in `EEG_Lab` (from `FingerRehab-EEGLab.zip` on the [release](https://github.com/basil2fxs/Hand-Rehab-Thesis/releases/latest)).
2. Run `Get PsychoPy.cmd` and install PsychoPy with its defaults.
3. Plug in the hand device and the trigger box, then run `Check this PC.cmd`. If it says a board has no driver, open the game: Settings, Setup, USB driver, Get the driver.
4. In the game: Settings, Setup, Audio delay, once.

## The simulator

Double-click `EEG simulator.cmd`: the simulator opens and plays the trigger box and the amplifier. Then start the game as at the lab (Run in PsychoPy, or double-click `Finger Rehab.exe`). It finds no box on COM10, finds the simulator and runs as if the box were plugged in; the menu says it is a rehearsal. A game already on the port list finds it on Scan again. With a second screen the simulator opens on it; on one screen, switch with Alt+Tab. Every marker shows up as a line on the simulated EEG, with its number and what it means on the right. The EEG is made up; the markers are the real bytes the lab box would get, with their pulse widths.

Keys in the simulator: Space pauses, Up and Down change the gain, Left and Right change the time span, S saves the markers to a CSV, Esc quits.

From source on any computer: `python3 main.py --eeg-simulator` in one terminal, `python3 main.py --config config/eeg_lab.yaml` in another.

For a real COM10, with the serial driver in the path too, install a virtual serial pair (com0com, COM10 to COM11) and start the simulator with `--sim-port COM11`.
