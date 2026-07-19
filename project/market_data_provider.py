from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

MARKET_DATA_DB_ENV = "GLOBAL_MARKET_MONITOR_DB_PATH"
MARKET_DATA_DIR_ENV = "GLOBAL_MARKET_MONITOR_DATA_DIR"


def resolve_market_data_dir() -> Path:
    override = os.getenv(MARKET_DATA_DIR_ENV, "").strip()
    if override:
        return Path(override)
    local_app_data = os.getenv("LOCALAPPDATA", "").strip()
    if local_app_data:
        return Path(local_app_data) / "GlobalMarketMonitor" / "market_data"
    return Path.home() / ".global_market_monitor" / "market_data"


def resolve_market_data_db_path() -> Path:
    override = os.getenv(MARKET_DATA_DB_ENV, "").strip()
    if override:
        return Path(override)
    return resolve_market_data_dir() / "market_data.sqlite3"


def utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()
