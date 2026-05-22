from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from project.historical_price_backfill import build_historical_price_backfill, write_historical_price_backfill


def test_historical_price_backfill_records_success_and_failure(tmp_path: Path) -> None:
    def downloader(ticker: str, start: str, end: str) -> pd.DataFrame:
        if ticker == "BAD":
            raise RuntimeError("not available")
        return pd.DataFrame({"Close": [100.0, 101.0]}, index=pd.to_datetime(["2026-01-02", "2026-01-03"]))

    payload = build_historical_price_backfill("2026-01-01", "2026-01-10", ["ACWI", "BAD"], downloader=downloader)
    summary = write_historical_price_backfill(payload, tmp_path / "historical_prices.csv", tmp_path)

    written = pd.read_csv(tmp_path / "historical_prices.csv")
    report = json.loads((tmp_path / "historical_price_backfill_summary.json").read_text(encoding="utf-8"))
    assert summary["ok_count"] == 1
    assert summary["failed_count"] == 1
    assert report["usable_start"] == "2026-01-02"
    assert report["usable_end"] == "2026-01-03"
    assert report["ticker_summary"][0]["usable_start"] == "2026-01-02"
    assert "ACWI" in written.columns
    assert report["ticker_summary"][1]["status"] == "failed"


def test_historical_price_backfill_extracts_multiindex_close() -> None:
    columns = pd.MultiIndex.from_tuples([("Close", "ACWI"), ("Open", "ACWI")])
    raw = pd.DataFrame([[100.0, 99.0], [102.0, 101.0]], columns=columns, index=pd.to_datetime(["2026-01-02", "2026-01-03"]))

    payload = build_historical_price_backfill("2026-01-01", "2026-01-10", ["ACWI"], downloader=lambda *_: raw)

    assert list(payload["prices"]["ACWI"]) == [100.0, 102.0]
