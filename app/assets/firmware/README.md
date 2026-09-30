`finger_rehab_nano.hex` (the game firmware), `singletact_address_change.hex` (the sensor address tool) and `manifest.json` (a checksum and details for each).
They are built from `arduino/`, not kept in git: `python3 builds/build_firmware.py` rebuilds them, and CI does it on every push so each app carries firmware from its own commit.
The app checks each hex against the manifest before flashing and refuses a damaged one.
