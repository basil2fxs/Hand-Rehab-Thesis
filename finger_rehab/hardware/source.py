"""Base classes for anything that produces FSR samples."""
from __future__ import annotations

import abc
import queue
import threading
import time
from dataclasses import dataclass


@dataclass
class Sample:
    t_perf: float            # time.perf_counter() at receive
    values: tuple[int, ...]  # 4 FSR values for one hand, 8 if both


class Source(abc.ABC):
    @abc.abstractmethod
    def start(self) -> None: ...

    @abc.abstractmethod
    def stop(self) -> None: ...

    @abc.abstractmethod
    def get_sample(self, timeout: float = 0.0) -> Sample | None: ...

    @abc.abstractmethod
    def send_command(self, cmd: str) -> bool: ...

    @property
    @abc.abstractmethod
    def is_connected(self) -> bool: ...

    @property
    def provides_samples(self) -> bool:
        # Override to False for fallback sources like the keyboard.
        return True

    @property
    def name(self) -> str:
        return type(self).__name__


class BaseQueueSource(Source):
    """Shared thread + queue machinery. Subclasses just implement _run."""

    def __init__(self, queue_max: int = 4096) -> None:
        self._q: queue.Queue[Sample] = queue.Queue(maxsize=queue_max)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name=self.name)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        # Drain so a restart doesn't deliver stale samples.
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass

    def get_sample(self, timeout: float = 0.0) -> Sample | None:
        try:
            if timeout > 0:
                return self._q.get(timeout=timeout)
            return self._q.get_nowait()
        except queue.Empty:
            return None

    def _push(self, values: tuple[int, ...]) -> None:
        s = Sample(t_perf=time.perf_counter(), values=values)
        try:
            self._q.put_nowait(s)
        except queue.Full:
            # Drop oldest. Better than blocking the producer thread.
            try:
                self._q.get_nowait()
                self._q.put_nowait(s)
            except queue.Empty:
                pass

    @abc.abstractmethod
    def _run(self) -> None: ...
