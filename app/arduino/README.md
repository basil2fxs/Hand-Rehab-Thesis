# arduino

<p align="center"><img src="../docs/images/device.jpg" width="620" alt="The hand device: a drawing of the board and pads, and three photos of the build"></p>
<p align="center"><sub><b>1</b> SingleTact pad and its board &middot; <b>2</b> Arduino Nano &middot; <b>3</b> USB cable &middot; <b>4</b> custom PCB &middot; <b>5</b> motor PCB<br><b>6</b> motor PCB connector &middot; <b>7</b> force sensor connector &middot; <b>8</b> threaded screw for finger adjustment<br>Parts, wiring, pins and the printed chassis: <a href="../../hardware">hardware</a></sub></p>

| Folder | What it is |
| --- | --- |
| [`firmware_on_device/`](firmware_on_device) | The game firmware: reads the four pads at 200 Hz and drives the four motors |
| [`singletact_address_change/`](singletact_address_change) | A small sketch that moves one sensor to a new I2C address |

The app flashes both from `../assets/firmware` (Settings, Setup), so the Arduino IDE is not needed. `python builds/build_firmware.py` rebuilds them with PlatformIO.
