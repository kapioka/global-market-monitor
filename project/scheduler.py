from __future__ import annotations

import time
from typing import Callable

import schedule


def run_scheduler(
    job: Callable[[], None],
    hour: int,
    minute: int,
    run_immediately: bool = False,
    sleep_seconds: int = 30,
) -> None:
    if run_immediately:
        job()
    schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(job)
    while True:
        schedule.run_pending()
        time.sleep(sleep_seconds)
