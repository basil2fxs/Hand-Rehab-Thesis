# SingleTact address tool

A small sketch that moves one SingleTact board to a new I2C address. The game firmware can't write to the sensors,
so this job has its own sketch. The app runs it for you: Settings, Setup, Sensor address flashes it, sends the
change, then puts the game firmware back.

## Commands

115200 baud, one command per line.

| Send | Reply |
| --- | --- |
| (boot) | `### ADDR TOOL 1 ###` |
| `VERSION` | `ADDRTOOL 1` |
| `SCAN` | `FOUND: 0x04,0x05,0x06` (or `FOUND: none`) |
| `CHANGE:0x04,0x05` | `OK: 0x04 -> 0x05` (or `ERR: reason`) |

## One sensor at a time

Every SingleTact board also answers address 0x04 (SingleTact manual, section 2.3), so a change sent to 0x04 reaches
every sensor on the bus. Change a sensor with only that one connected.

## Building it by hand

```bash
pio run -d arduino/singletact_address_change -e nanoatmega328new
```

`builds/build_firmware.py` does this and copies the hex into `assets/firmware/`, where the app looks for it.
