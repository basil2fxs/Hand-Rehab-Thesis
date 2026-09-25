# arduino

| Folder | What it is |
| --- | --- |
| [`firmware_on_device/`](firmware_on_device) | The game firmware for the Arduino Nano: reads the four pads at 200 Hz and drives the four motors |
| [`singletact_address_change/`](singletact_address_change) | A short-lived sketch that moves one sensor to a new I2C address |

Nobody needs the Arduino IDE. The built hexes ship in [`../assets/firmware`](../assets/firmware), and Settings
flashes them (Flash firmware, Sensor address). `python builds/build_firmware.py` rebuilds both with PlatformIO,
and the build-apps run on GitHub does the same.

<sub>[Back to app](../README.md)</sub>
