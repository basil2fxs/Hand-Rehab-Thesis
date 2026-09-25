# Game firmware (PlatformIO)

The sketch the Arduino Nano runs in play: it reads the four SingleTact pads at 200 Hz, streams them to the laptop
and drives the four motors on `STIM` commands. Settings, Flash firmware installs the built hex, so these steps are
only for building it by hand.

1. **Board.** A Nano labelled NANO is `board = nanoatmega328`; a Nano with no label is
   `board = nanoatmega328new`. Set it in `platformio.ini`.
2. **Port.** In a terminal, `mode` (Windows) lists the COM ports; unplug the board and run it again, and the one
   that disappears is the board. Put it in `platformio.ini` as `upload_port` and `monitor_port`.
3. **Upload, then start the game.** The board buzzes all four motors on connect (about 1.6 s) and then streams.

The game finds the board on its own; nothing needs setting on the Python side. These steps came with the
handover from the 2025 build.

<sub>[Back to arduino](../README.md)</sub>
