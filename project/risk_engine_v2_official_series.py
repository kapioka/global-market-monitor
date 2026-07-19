from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from project.config_loader import load_config
from project.data_fetcher import fetch_market_data


def official_series_tickers(config: dict[str, Any]) -> list[str]:
    settings = config.get("risk_engine_v2", {}) if isinstance(config, dict) else {}
    official = settings.get("official_series", {}) if isinstance(settings, dict) else {}
    tickers: list[str] = []
    for ticker in official.values():
        text = str(ticker or "")
        if text and text not in tickers:
            tickers.append(text)
    return tickers


def merge_official_series(prices: pd.DataFrame, official_prices: pd.DataFrame) -> pd.DataFrame:
    if official_prices.empty:
        return prices
    merged = _normalize_frame(prices).copy()
    official = _normalize_frame(official_prices)
    merged = merged.join(official, how="outer", rsuffix="__official")
    for column in list(merged.columns):
        if column.endswith("__official"):
            base = column.removesuffix("__official")
            merged[base] = merged[column].combine_first(merged.get(base))
            merged = merged.drop(columns=[column])
    merged = merged.sort_index()
    merged.attrs = {"input_row_count": len(merged), "input_duplicate_date_count": 0}
    return merged


def load_official_series_csv(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path, index_col=0)
    frame.index.name = "date"
    return _validate_and_normalize_frame(frame, source=str(path))


def run_risk_engine_v2_official_series_fetch(
    *,
    config_path: str | Path = "project/config.yaml",
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    config = load_config(config_path)
    tickers = official_series_tickers(config)
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    if not tickers:
        return {"status": "missing_official_series_config", "tickers": []}
    logger = logging.getLogger("risk_engine_v2_official_series")
    fetch = fetch_market_data(
        tickers=tickers,
        period_years=int(config.get("data", {}).get("period_years", 10)),
        interval=str(config.get("data", {}).get("interval", "1wk")),
        logger=logger,
        use_sample_on_failure=False,
        cache_dir=config.get("paths", {}).get("cache_dir"),
    )
    csv_path = reports_path / "risk_engine_v2_official_series.csv"
    json_path = reports_path / "risk_engine_v2_official_series.json"
    fetched_prices = _validate_and_normalize_frame(fetch.prices, source="fetched official series")
    existing_prices = load_official_series_csv(csv_path) if csv_path.exists() else pd.DataFrame()
    merged_prices = merge_official_series(existing_prices, fetched_prices)
    provenance = _merge_provenance(existing_prices, fetched_prices, merged_prices)
    payload = {
        "status": "ok" if set(tickers).issubset(set(fetched_prices.columns)) else "partial",
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "tickers": tickers,
        "columns": list(merged_prices.columns),
        "source": fetch.source,
        "warnings": fetch.warnings,
        "acquisition_log": fetch.acquisition_log,
        "csv_path": str(csv_path),
        "history_merge": provenance,
    }
    _atomic_write_csv(merged_prices, csv_path)
    _atomic_write_text(json.dumps(payload, ensure_ascii=False, indent=2), json_path)
    return {
        "status": payload["status"],
        "csv_path": str(csv_path),
        "json_path": str(json_path),
        "columns": payload["columns"],
        "warnings": fetch.warnings,
    }


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    clean = frame.copy()
    clean.index = pd.to_datetime(clean.index, errors="coerce").tz_localize(None)
    clean = clean[clean.index.notna()]
    clean = clean.sort_index()
    clean = clean[~clean.index.duplicated(keep="last")]
    return clean.apply(pd.to_numeric, errors="coerce")


def _validate_and_normalize_frame(frame: pd.DataFrame, *, source: str) -> pd.DataFrame:
    if frame.empty:
        raise ValueError(f"{source} is empty")
    if frame.columns.duplicated().any():
        raise ValueError(f"{source} contains duplicate columns")
    parsed_index = pd.to_datetime(frame.index, errors="coerce")
    if parsed_index.isna().any():
        raise ValueError(f"{source} contains invalid dates")
    numeric = frame.apply(pd.to_numeric, errors="coerce")
    invalid_values = frame.notna() & numeric.isna()
    if invalid_values.any().any():
        raise ValueError(f"{source} contains non-numeric values")
    normalized = _normalize_frame(frame)
    normalized.attrs["input_row_count"] = len(frame)
    normalized.attrs["input_duplicate_date_count"] = int(parsed_index.duplicated(keep=False).sum())
    return normalized


def _frame_summary(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "row_count": 0,
            "input_row_count": 0,
            "start_date": None,
            "end_date": None,
            "input_duplicate_date_count": 0,
            "duplicate_date_count": 0,
        }
    return {
        "row_count": len(frame),
        "input_row_count": int(frame.attrs.get("input_row_count", len(frame))),
        "start_date": frame.index.min().date().isoformat(),
        "end_date": frame.index.max().date().isoformat(),
        "input_duplicate_date_count": int(frame.attrs.get("input_duplicate_date_count", frame.index.duplicated(keep=False).sum())),
        "duplicate_date_count": int(frame.index.duplicated(keep=False).sum()),
    }


def _merge_provenance(
    existing: pd.DataFrame,
    fetched: pd.DataFrame,
    merged: pd.DataFrame,
) -> dict[str, Any]:
    return {
        "strategy": "retain_existing_prefer_fetched_on_overlap",
        "existing_store_present": not existing.empty,
        "existing": _frame_summary(existing),
        "fetched": _frame_summary(fetched),
        "merged": _frame_summary(merged),
        "overlap_date_count": len(existing.index.intersection(fetched.index)),
    }


def _atomic_write_csv(frame: pd.DataFrame, path: Path) -> None:
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(handle)
    temporary_path = Path(temporary_name)
    try:
        frame.to_csv(temporary_path)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _atomic_write_text(text: str, path: Path) -> None:
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(handle)
    temporary_path = Path(temporary_name)
    try:
        temporary_path.write_text(text, encoding="utf-8")
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch diagnostic official risk_engine_v2 FRED series.")
    parser.add_argument("--config", default="project/config.yaml")
    parser.add_argument("--reports-dir", default="project/reports")
    args = parser.parse_args()
    print(
        json.dumps(
            run_risk_engine_v2_official_series_fetch(config_path=args.config, reports_dir=args.reports_dir),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
