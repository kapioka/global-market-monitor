from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from project.data_fetcher import FetchResult


def fetch_snapshot_observed_at() -> str:
    return datetime.now().isoformat(timespec="seconds")


def snapshot_archive_dir(cache_dir: str | Path) -> Path:
    return Path(cache_dir) / "market_snapshots"


def snapshot_exists_for_slot(cache_dir: str | Path, snapshot_date: date, slot: tuple[int, int]) -> bool:
    hour, minute = slot
    return _snapshot_prices_path(cache_dir, f"{snapshot_date.isoformat()}T{hour:02d}:{minute:02d}:00").exists()


def save_fetch_snapshot(fetch: FetchResult, cache_dir: str | Path, observed_at: str, logger: Any) -> None:
    archive_dir = snapshot_archive_dir(cache_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)
    prices_path = _snapshot_prices_path(cache_dir, observed_at)
    metadata_path = _snapshot_metadata_path(cache_dir, observed_at)
    fetch.prices.to_csv(prices_path, encoding="utf-8")
    metadata = {
        "observed_at": observed_at,
        "source": fetch.source,
        "warnings": fetch.warnings,
        "acquisition_log": fetch.acquisition_log,
        "diagnostics": fetch.diagnostics,
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved market snapshot archive to %s", prices_path)


def load_fetch_snapshot(cache_dir: str | Path, snapshot_date: date, slot: tuple[int, int]) -> FetchResult | None:
    hour, minute = slot
    observed_at = f"{snapshot_date.isoformat()}T{hour:02d}:{minute:02d}:00"
    prices_path = _snapshot_prices_path(cache_dir, observed_at)
    metadata_path = _snapshot_metadata_path(cache_dir, observed_at)
    return _load_fetch_snapshot_files(prices_path, metadata_path)


def load_latest_fetch_snapshot(cache_dir: str | Path) -> FetchResult | None:
    for metadata_path in sorted(snapshot_archive_dir(cache_dir).glob("market_snapshot_*.json"), reverse=True):
        fetch = _load_fetch_snapshot_files(metadata_path.with_suffix(".csv"), metadata_path)
        if fetch is not None:
            return fetch
    return None


def _load_fetch_snapshot_files(prices_path: Path, metadata_path: Path) -> FetchResult | None:
    if not prices_path.exists() or not metadata_path.exists():
        return None

    prices = pd.read_csv(prices_path, index_col=0, parse_dates=True)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    diagnostics = dict(metadata.get("diagnostics", {}))
    summary = dict(diagnostics.get("summary", {}))
    summary.setdefault("source", str(metadata.get("source", "snapshot")))
    summary["snapshot_observed_at"] = metadata.get("observed_at")
    summary["snapshot_metadata_path"] = str(metadata_path)
    summary["snapshot_prices_path"] = str(prices_path)
    diagnostics["summary"] = summary
    return FetchResult(
        prices=prices,
        warnings=list(metadata.get("warnings", [])),
        source=str(metadata.get("source", "snapshot")),
        acquisition_log=list(metadata.get("acquisition_log", [])),
        diagnostics=diagnostics,
    )


def _snapshot_prices_path(cache_dir: str | Path, observed_at: str) -> Path:
    return snapshot_archive_dir(cache_dir) / f"market_snapshot_{_timestamp_slug(observed_at)}.csv"


def _snapshot_metadata_path(cache_dir: str | Path, observed_at: str) -> Path:
    return snapshot_archive_dir(cache_dir) / f"market_snapshot_{_timestamp_slug(observed_at)}.json"


def _timestamp_slug(value: str) -> str:
    return value.replace(":", "").replace("T", "_").split("+", 1)[0]
