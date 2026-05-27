"""Keyboard-only source. Used when no Arduino is plugged in."""
from __future__ import annotations

import logging

from .source import BaseQueueSource


log = logging.getLogger(__name__)


class KeyboardOnlySource(BaseQueueSource):
    @property
    def name(self) -> str:
        return "KeyboardOnlySource"

    @property
    def provides_samples(self) -> bool:
        # We're alive but never push FSR data. The game layer reads pygame KEYDOWN
        # events directly as the press surrogate.
        return False

    def _run(self) -> None:
        self._connected = True
        log.info("Keyboard-only source running (no FSR data)")
        self._stop.wait()
        self._connected = False

    def send_command(self, cmd: str) -> bool:
        log.debug("Keyboard mode ignoring command: %s", cmd)
        return False
