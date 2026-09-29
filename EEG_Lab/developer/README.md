# Developer

Tools for setting up and rehearsing the lab session. This folder stays on my PC and doesn't go to the lab (the release's `FingerRehab-EEGLab.zip` leaves it out).

| | |
| --- | --- |
| `EEG simulator.cmd` | Rehearse the lab without the lab: a window stands in for the trigger box and the amplifier, and the game sends its markers there instead of COM10 |
| `Get PsychoPy.cmd` | Downloads the Standalone PsychoPy installer (2026.2.4, about 530 MB) into `downloads/` and runs it |
| `Check this PC.cmd` | Checks the game's flashing tools and the USB driver of any Arduino plugged in |

## A new PC

1. Put the latest `Finger Rehab.exe` in `EEG_Lab` (from `FingerRehab-EEGLab.zip` on the [release](https://github.com/basil2fxs/Hand-Rehab-Thesis/releases/latest)).
2. Run `Get PsychoPy.cmd` and install PsychoPy with its defaults.
3. Plug in the hand device and the trigger box, then run `Check this PC.cmd`. If it says a board has no driver, open the game: Settings, Setup, USB driver, Get the driver.
4. In the game: Settings, Setup, Audio delay, once.

## The simulator

Double-click `EEG simulator.cmd`. Two windows open: the simulator, then the game in lab mode, in a window rather than fullscreen. With a second screen the simulator opens on it. On one screen, switch between them with Alt+Tab (the simulator window can be dragged to any size). Play as in the lab and every marker shows up as a line on the simulated EEG, with its number and what it means on the right. The EEG is made up; the markers are the real bytes the lab box would get, with their pulse widths.

Keys in the simulator: Space pauses, Up and Down change the gain, Left and Right change the time span, S saves the markers to a CSV, Esc quits.

From source on any computer: `python3 main.py --eeg-simulator` in one terminal, `python3 main.py --config config/eeg_lab.yaml --eeg-port socket://127.0.0.1:50410` in another.

To have the game use COM10 exactly as in the lab, install a virtual serial pair (com0com, COM10 to COM11) and start the simulator with `--sim-port COM11`.
