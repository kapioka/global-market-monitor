from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any


HISTORY_FILENAME_RE = re.compile(r"report_(\d{4}-\d{2}-\d{2})_(\d{2})(\d{2})(\d{2})\.json$")


def history_slot_time(config: dict[str, Any]) -> tuple[int, int]:
    scheduler_config = config.get("scheduler", {})
    return int(scheduler_config.get("hour", 7)), int(scheduler_config.get("minute", 30))


def existing_history_slots(reports_dir: str | Path) -> set[tuple[date, int, int]]:
    history_dir = Path(reports_dir) / "history"
    if not history_dir.exists():
        return set()

    slots: set[tuple[date, int, int]] = set()
    for file_path in history_dir.glob("report_*.json"):
        match = HISTORY_FILENAME_RE.match(file_path.name)
        if match:
            slots.add(
                (
                    date.fromisoformat(match.group(1)),
                    int(match.group(2)),
                    int(match.group(3)),
                )
            )
    return slots


def compute_backfill_dates(
    config: dict[str, Any],
    reports_dir: str | Path,
    today: date,
    max_backfill_days: int,
) -> list[date]:
    if max_backfill_days <= 0:
        return []

    target_hour, target_minute = history_slot_time(config)
    existing = existing_history_slots(reports_dir)
    yesterday = today - timedelta(days=1)
    window_start = today - timedelta(days=max_backfill_days)
    if yesterday < window_start:
        return []

    missing: list[date] = []
    cursor = window_start
    while cursor <= yesterday:
        if (cursor, target_hour, target_minute) not in existing:
            missing.append(cursor)
        cursor += timedelta(days=1)
    return missing


def existing_history_files_for_date(reports_dir: str | Path, target_date: date) -> list[Path]:
    history_dir = Path(reports_dir) / "history"
    if not history_dir.exists():
        return []
    prefix = f"report_{target_date.isoformat()}_"
    return sorted(history_dir.glob(f"{prefix}*.json"))
