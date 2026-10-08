# arduino

<p align="center"><img src="../docs/images/device.jpg" width="620" alt="The hand device: a drawing of the board and pads, and three photos of the build"></p>
<p align="center"><sub><b>1</b> SingleTact pad and its board &middot; <b>2</b> Arduino Nano &middot; <b>3</b> USB cable &middot; <b>4</b> custom PCB &middot; <b>5</b> motor PCB<br><b>6</b> motor PCB connector &middot; <b>7</b> force sensor connector &middot; <b>8</b> threaded screw for finger adjustment<br>Parts, wiring, pins and the printed chassis: <a href="../../hardware">hardware</a></sub></p>

| Folder | What it is |
| --- | --- |
| [`firmware_on_device/`](firmware_on_device) | The game firmware: reads the four pads at 200 Hz, sends them over USB and buzzes the motors on `STIM` commands. `lib/` holds Config (pins, addresses, the I2C read), Motor and Sensor |
| [`singletact_address_change/`](singletact_address_change) | A small sketch that moves one sensor to a new I2C address |

## Flashing

Settings, Setup flashes both from `../assets/firmware` with the avrdude bundled in the app, so the Arduino IDE is not needed. `Finger Rehab --check-tools report.json` checks those tools by hand.

- **Flash firmware:** press, confirm, wait about ten seconds. The board restarts and buzzes all four motors. The line under Firmware names the hex the app carries.
- **Sensor address:** connect ONE sensor, enter the old and new address, confirm. The app flashes the address tool, moves the sensor, then puts the game firmware back; Scan lists what answers. Every SingleTact also answers 0x04 (SingleTact manual, section 2.3), so the app refuses a change from 0x04 with other sensors wired in. The device wants 0x05 index, 0x06 middle, 0x07 ring, 0x08 little.

When it goes wrong (the full avrdude output is in the app log):

- **No Arduino found:** plug it in. No port at all on Windows means the board's USB chip (CH340) has no driver yet: Setup, USB driver, Get the driver. macOS 10.14 and later need none.
- **Did not answer at 115200 or 57600:** the app tries both Nano bootloaders. Check the cable (some are charge only), unplug and replug, try again.
- **Could not open the port:** close the Arduino IDE, any serial monitor or another copy of the app.
- **"The GAME firmware is NOT on the board":** press Flash firmware.
- **This Mac needs Rosetta:** run `softwareupdate --install-rosetta` in Terminal once.

## Building by hand

`python3 builds/build_firmware.py` (PlatformIO) rebuilds both hexes into `assets/firmware/`, and `python3 builds/fetch_avrdude.py` fetches the uploader; the build scripts and CI run both. To upload the game firmware from PlatformIO instead, set `board` in `firmware_on_device/platformio.ini` (`nanoatmega328` for a Nano labelled NANO, `nanoatmega328new` otherwise) and `upload_port`. The board buzzes all four motors when it connects (about 1.6 s), then streams. The address tool: `pio run -d arduino/singletact_address_change -e nanoatmega328new`.

The address tool talks at 115200 baud, one command per line:

| Send | Reply |
| --- | --- |
| (boot) | `### ADDR TOOL 1 ###` |
| `VERSION` | `ADDRTOOL 1` |
| `SCAN` | `FOUND: 0x04,0x05,0x06` (or `FOUND: none`) |
| `CHANGE:0x04,0x05` | `OK: 0x04 -> 0x05` (or `ERR: reason`) |
