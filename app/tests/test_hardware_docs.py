"""hardware/README.md is what somebody builds the device from. Its pins,
addresses and timings are read here from the firmware and the actuator
sketch themselves, so a wiring change that is not written down fails
instead of leaving a wrong table for the next builder.
"""
from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path
from urllib.parse import unquote

REPO = Path(__file__).resolve().parents[2]
HW = REPO / "hardware"
README = HW / "README.md"
FIRMWARE = REPO / "app" / "arduino" / "firmware_on_device" / "lib" / "Config"
SKETCH = HW / "linear_actuator" / "linear_actuator.ino"


class HardwareDocsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = README.read_text(encoding="utf-8")

    def test_plain_ascii(self) -> None:
        self.assertTrue(self.text.isascii())

    def test_links_resolve(self) -> None:
        for target in re.findall(r"(?:\]\(|src=\")(?!https?://|#)([^)\"#]+)",
                                 self.text):
            with self.subTest(link=target):
                self.assertTrue((HW / unquote(target)).exists(), target)

    def test_the_motor_pins_are_the_firmware_pins(self) -> None:
        header = (FIRMWARE / "Config.h").read_text(encoding="utf-8")
        for finger, name in (("Index", "INDEX"), ("Middle", "MIDDLE"),
                             ("Ring", "RING"), ("Little", "PINKY")):
            pin = re.search(rf"#define PIN_MOTOR_{name}\s+(\d+)", header)
            self.assertIsNotNone(pin, name)
            with self.subTest(finger=finger):
                self.assertIn(f"| D{pin.group(1)} | {finger} finger motor |",
                              self.text)

    def test_the_pad_addresses_are_the_firmware_addresses(self) -> None:
        header = (FIRMWARE / "Config.h").read_text(encoding="utf-8")
        for finger, name in (("index", "INDEX"), ("middle", "MIDDLE"),
                             ("ring", "RING"), ("little", "PINKY")):
            addr = re.search(rf"#define FSR_{name}\s+(0x[0-9A-Fa-f]+)", header)
            self.assertIsNotNone(addr, name)
            with self.subTest(finger=finger):
                self.assertIn(f"{finger} {addr.group(1)}", self.text)

    def test_rate_and_buzz_are_the_firmware_values(self) -> None:
        body = (FIRMWARE / "Config.cpp").read_text(encoding="utf-8")
        rate = re.search(r"sampleRate\s*=\s*(\d+)", body).group(1)
        buzz = re.search(r"STIM_ON_MS\s*=\s*(\d+)", body).group(1)
        self.assertIn(f"{rate} times a second", self.text)
        self.assertIn(f"for {buzz} ms", self.text)

    def test_the_actuator_pins_are_the_sketch_pins(self) -> None:
        sketch = SKETCH.read_text(encoding="utf-8")

        def pin(name: str) -> str:
            return re.search(rf"const int {name}\s*=\s*(\d+);",
                             sketch).group(1)

        self.assertIn(f"| D{pin('IN1')}, D{pin('IN2')} | Driver IN1 and IN2",
                      self.text)
        self.assertIn(f"| D{pin('ENA')} | Driver ENA", self.text)
        self.assertIn(f"| D{pin('BTN_EXTEND')} | Extend button", self.text)
        self.assertIn(f"| D{pin('BTN_RETRACT')} | Retract button", self.text)

    def test_the_print_files_are_real_meshes(self) -> None:
        for name in ("base.stl", "top.stl", "fingers.stl"):
            data = (HW / "cad" / name).read_bytes()
            triangles = struct.unpack_from("<I", data, 80)[0]
            with self.subTest(file=name):
                self.assertGreater(triangles, 100)
                self.assertEqual(len(data), 84 + 50 * triangles)
        self.assertGreater((HW / "cad" / "hand_device_v1.f3d").stat().st_size,
                           100_000)


if __name__ == "__main__":
    unittest.main()
