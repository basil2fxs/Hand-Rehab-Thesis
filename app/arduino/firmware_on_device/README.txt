Firmware setup (PlatformIO)
===========================

1. Board
   Nano labelled NANO:     board = nanoatmega328
   Nano with no label:     board = nanoatmega328new
   Set it in platformio.ini.

2. COM port
   Open a terminal and type: mode
   Note the COM port listed (eg COM7). If unsure which one is the
   board, unplug it and run mode again: the one that disappears is
   it.
   Put it in platformio.ini:
     upload_port = COMX
     monitor_port = COMX

3. Upload, then start the game. The board self-tests its motors on
   connect (about 1.6 s of buzzing) and then streams sensor data.

The game finds the board on its own, so nothing needs setting on the
Python side. These notes came with the handover from the 2025 build.
