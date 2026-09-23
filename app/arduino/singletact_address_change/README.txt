SingleTact address tool
=======================

What this is
------------
A throwaway sketch that moves one SingleTact interface board from one
I2C address to another. It replaces the game firmware on the Nano for a
few seconds and is then replaced by the game firmware again. The game
firmware in arduino/firmware_on_device is read only and has no I2C
write command, which is why the job needs its own sketch.

Who runs it
-----------
The app. Settings -> Change sensor address flashes this hex, talks to
it over serial, then flashes the game hex back. Nobody has to open the
Arduino IDE.

Serial protocol, 115200 baud, one command per line
--------------------------------------------------
  boot              -> ### ADDR TOOL 1 ###
  VERSION           -> ADDRTOOL 1
  SCAN              -> FOUND: 0x04,0x05,0x06   (or FOUND: none)
  CHANGE:0x04,0x05  -> OK: 0x04 -> 0x05        (or ERR: reason)

The one rule that matters
-------------------------
Every SingleTact interface answers I2C address 0x04 as well as the
address held in its own flash (SingleTact manual section 2.3). A write
to 0x04 therefore reaches every sensor on the bus at once. Change a
sensor from 0x04 with only that one sensor connected, or all of them
end up on the same address.

Building it by hand
-------------------
  pio run -d arduino/singletact_address_change -e nanoatmega328new

The hex lands in .pio/build/nanoatmega328new/firmware.hex.
builds/build_firmware.py does this and copies the result into
assets/firmware/ where the app looks for it.
