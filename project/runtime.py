from __future__ import annotations

import logging
import sys
import threading
import time
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterable, Iterator


def ensure_directories(paths: Iterable[str | Path]) -> None:
    for path in paths:
        Path(path).mkdir(parents=True, exist_ok=True)


def setup_logging(log_dir: str | Path, level: str = "INFO") -> logging.Logger:
    ensure_directories([log_dir])
    logger = logging.getLogger("market_monitor")
    if logger.handlers:
        return logger

    logger.setLevel(level.upper())
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler = RotatingFileHandler(
        Path(log_dir) / "app.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


class ConsoleSpinner:
    def __init__(self, message: str = "処理中", stream=None, interval_seconds: float = 0.12) -> None:
        self.message = message
        self.stream = stream or sys.stdout
        self.interval_seconds = interval_seconds
        self._frames = "|/-\\"
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.enabled = bool(getattr(self.stream, "isatty", lambda: False)())

    def start(self) -> None:
        if not self.enabled or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._spin, name="console-spinner", daemon=True)
        self._thread.start()

    def stop(self, final_message: str | None = None) -> None:
        if not self.enabled:
            return
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        clear = "\r" + (" " * (len(self.message) + 8)) + "\r"
        self.stream.write(clear)
        if final_message:
            self.stream.write(final_message + "\n")
        self.stream.flush()

    def _spin(self) -> None:
        idx = 0
        while not self._stop_event.is_set():
            frame = self._frames[idx % len(self._frames)]
            self.stream.write(f"\r{frame} {self.message}")
            self.stream.flush()
            idx += 1
            time.sleep(self.interval_seconds)


@contextmanager
def console_spinner(message: str) -> Iterator[ConsoleSpinner]:
    spinner = ConsoleSpinner(message)
    spinner.start()
    try:
        yield spinner
    finally:
        spinner.stop()
