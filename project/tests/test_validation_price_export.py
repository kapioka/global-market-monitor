from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd
import pytest

from project.data_fetcher import FetchResult
from project.validation_price_export import export_validation_prices, series_to_price_points


def test_series_to_price_points_sorts_and_drops_missing_values() -> None:
    series = pd.Series(
        [105.1234567, None, 100.0],
        index=pd.to_datetime(["2026-01-09", "2026-01-16", "2026-01-02"]),
        name="ACWI",
    )

    assert series_to_price_points(series) == [
        {"date": "2026-01-02", "price": 100.0},
        {"date": "2026-01-09", "price": 105.123457},
    ]


def test_export_validation_prices_writes_live_payload(tmp_path: Path) -> None:
    def fetcher(tickers, period_years, interval, logger, use_sample_on_failure, cache_dir, force_sample):
        assert tickers == ["ACWI"]
        assert period_years == 10
        assert interval == "1wk"
        assert use_sample_on_failure is False
        assert force_sample is False
        prices = pd.DataFrame({"ACWI": [100.0, 101.5]}, index=pd.to_datetime(["2026-01-02", "2026-01-09"]))
        return FetchResult(
            prices=prices,
            warnings=[],
            source="yfinance",
            acquisition_log=[{"requested_ticker": "ACWI", "used_ticker": "ACWI", "status": "ok"}],
            diagnostics={},
        )

    output = tmp_path / "validation_prices.json"
    summary = export_validation_prices("ACWI", output, 10, "1wk", fetcher=fetcher, logger=logging.getLogger("test"))

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert summary["status"] == "ok"
    assert summary["point_count"] == 2
    assert payload["prices"][1] == {"date": "2026-01-09", "price": 101.5}


def test_export_validation_prices_rejects_proxy_by_default(tmp_path: Path) -> None:
    def fetcher(tickers, period_years, interval, logger, use_sample_on_failure, cache_dir, force_sample):
        prices = pd.DataFrame({"ACWI": [100.0, 101.5]}, index=pd.to_datetime(["2026-01-02", "2026-01-09"]))
        return FetchResult(
            prices=prices,
            warnings=[],
            source="yfinance",
            acquisition_log=[{"requested_ticker": "ACWI", "used_ticker": "VT", "status": "proxy_fallback"}],
            diagnostics={},
        )

    with pytest.raises(RuntimeError, match="proxy fallback"):
        export_validation_prices("ACWI", tmp_path / "validation_prices.json", 10, "1wk", fetcher=fetcher)


def test_export_validation_prices_allows_proxy_when_explicit(tmp_path: Path) -> None:
    def fetcher(tickers, period_years, interval, logger, use_sample_on_failure, cache_dir, force_sample):
        prices = pd.DataFrame({"ACWI": [100.0, 101.5]}, index=pd.to_datetime(["2026-01-02", "2026-01-09"]))
        return FetchResult(
            prices=prices,
            warnings=[],
            source="yfinance",
            acquisition_log=[{"requested_ticker": "ACWI", "used_ticker": "VT", "status": "proxy_fallback"}],
            diagnostics={},
        )

    summary = export_validation_prices(
        "ACWI",
        tmp_path / "validation_prices.json",
        10,
        "1wk",
        allow_proxy=True,
        fetcher=fetcher,
    )

    assert summary["status"] == "proxy_fallback"
    assert summary["used_ticker"] == "VT"
