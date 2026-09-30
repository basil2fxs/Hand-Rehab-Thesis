# Game firmware (PlatformIO)

What the Arduino Nano runs during play: it reads the four SingleTact pads at 200 Hz, sends them to the computer
and buzzes the motors on `STIM` commands. Settings, Setup, Flash firmware installs it, so these steps are only for
building it by hand.

1. **Board.** A Nano labelled NANO is `board = nanoatmega328`; an unlabelled one is `board = nanoatmega328new`.
   Set it in `platformio.ini`.
2. **Port.** Run `mode` (Windows) with the board plugged in and again without it; the COM port that disappears is
   the board. Put it in `platformio.ini` as `upload_port` and `monitor_port`.
3. **Upload, then start the game.** The board buzzes all four motors when it connects (about 1.6 s), then streams.
