from __future__ import annotations

import logging

import pandas as pd

import project.data_fetcher as data_fetcher
from project.sample_data import build_sample_prices

JAPAN_RESIDENT_SAMPLE_TICKERS = {"2510.T", "1343.T", "1540.T", "1321.T", "EURJPY=X"}


class DummyYF:
    def download(self, *args, **kwargs):
        raise RuntimeError("Failed to connect to fc.yahoo.com port 443")


def test_fetch_market_data_records_sample_fallback(monkeypatch):
    monkeypatch.setattr(data_fetcher, "yf", DummyYF())
    result = data_fetcher.fetch_market_data(
        tickers=["SPY"],
        period_years=10,
        interval="1wk",
        logger=logging.getLogger("test"),
        use_sample_on_failure=True,
    )
    assert "SPY" in result.prices.columns
    assert result.acquisition_log[0]["status"] == "sample_fallback"
    assert result.acquisition_log[0]["provider"] == "synthetic_sample"
    assert result.diagnostics["summary"]["suspected_network_issue"] is True
    assert "fc.yahoo.com" in result.diagnostics["suspected_hosts"]


def test_fetch_market_data_marks_unavailable_without_sample(monkeypatch):
    monkeypatch.setattr(data_fetcher, "yf", DummyYF())
    monkeypatch.setattr(data_fetcher, "build_sample_prices", lambda: pd.DataFrame())
    result = data_fetcher.fetch_market_data(
        tickers=["NON_EXISTENT"],
        period_years=10,
        interval="1wk",
        logger=logging.getLogger("test"),
        use_sample_on_failure=False,
    )
    assert result.prices.empty
    assert result.acquisition_log[0]["status"] == "unavailable"
    assert result.diagnostics["summary"]["failed_attempt_count"] >= 1


def test_fetch_market_data_supports_fred_series(monkeypatch):
    monkeypatch.setattr(data_fetcher, "yf", None)

    def fake_read_csv(url: str, timeout: int = 20, headers: dict | None = None):
        assert "MORTGAGE30US" in url
        return pd.DataFrame(
            {
                "DATE": ["2026-01-02", "2026-01-09", "2026-01-16"],
                "MORTGAGE30US": [6.91, 6.88, 6.84],
            }
        )

    monkeypatch.setattr(data_fetcher, "_read_csv_from_url", fake_read_csv)
    monkeypatch.setattr(
        data_fetcher,
        "build_sample_prices",
        lambda: pd.DataFrame({"FRED:MORTGAGE30US": [6.7, 6.75]}, index=pd.date_range("2025-01-03", periods=2, freq="W-FRI")),
    )

    result = data_fetcher.fetch_market_data(
        tickers=["FRED:MORTGAGE30US"],
        period_years=10,
        interval="1wk",
        logger=logging.getLogger("test"),
        use_sample_on_failure=True,
    )

    assert "FRED:MORTGAGE30US" in result.prices.columns
    assert result.acquisition_log[0]["provider"] == "fred"
    assert result.acquisition_log[0]["status"] == "ok"


def test_fetch_market_data_supports_fred_observation_date_column(monkeypatch):
    monkeypatch.setattr(data_fetcher, "yf", None)

    def fake_read_csv(url: str, timeout: int = 20, headers: dict | None = None):
        return pd.DataFrame(
            {
                "observation_date": ["2026-01-02", "2026-01-09", "2026-01-16"],
                "value": [0.1, 0.2, 0.3],
            }
        )

    monkeypatch.setattr(data_fetcher, "_read_csv_from_url", fake_read_csv)

    result = data_fetcher.fetch_market_data(
        tickers=["FRED:NFCI"],
        period_years=10,
        interval="1wk",
        logger=logging.getLogger("test"),
        use_sample_on_failure=False,
    )

    assert "FRED:NFCI" in result.prices.columns
    assert result.prices["FRED:NFCI"].iloc[-1] == 0.3
    assert result.acquisition_log[0]["status"] == "ok"


def test_fetch_market_data_supports_official_risk_engine_v2_fred_series(monkeypatch):
    monkeypatch.setattr(data_fetcher, "yf", None)
    requested: list[str] = []

    def fake_read_csv(url: str, timeout: int = 20, headers: dict | None = None):
        series_id = url.split("id=", 1)[1]
        requested.append(series_id)
        return pd.DataFrame(
            {
                "DATE": ["2026-01-02", "2026-01-09", "2026-01-16"],
                series_id: [1.0, 1.1, 1.2],
            }
        )

    monkeypatch.setattr(data_fetcher, "_read_csv_from_url", fake_read_csv)

    tickers = [
        "FRED:BAMLH0A0HYM2",
        "FRED:BAMLC0A0CM",
        "FRED:DFII10",
        "FRED:T10YIE",
        "FRED:T10Y2Y",
        "FRED:T10Y3M",
        "FRED:NFCI",
    ]
    result = data_fetcher.fetch_market_data(
        tickers=tickers,
        period_years=10,
        interval="1wk",
        logger=logging.getLogger("test"),
        use_sample_on_failure=False,
    )

    assert set(result.prices.columns) == set(tickers)
    assert {entry["provider"] for entry in result.acquisition_log} == {"fred"}
    assert {entry["status"] for entry in result.acquisition_log} == {"ok"}
    assert result.acquisition_log[0]["requested_ticker_name_ja"] == "米ハイイールドOAS"
    assert requested == [ticker.split(":", 1)[1] for ticker in tickers]


def test_fetch_market_data_marks_official_fred_unavailable_without_sample(monkeypatch):
    monkeypatch.setattr(data_fetcher, "yf", None)

    def fake_read_csv(url: str, timeout: int = 20, headers: dict | None = None):
        raise RuntimeError("FRED temporary failure")

    monkeypatch.setattr(data_fetcher, "_read_csv_from_url", fake_read_csv)

    result = data_fetcher.fetch_market_data(
        tickers=["FRED:BAMLH0A0HYM2"],
        period_years=10,
        interval="1wk",
        logger=logging.getLogger("test"),
        use_sample_on_failure=False,
    )

    assert result.prices.empty
    assert result.acquisition_log[0]["status"] == "unavailable"
    assert result.acquisition_log[0]["provider"] == "none"
    assert result.acquisition_log[0]["attempts"][0]["symbol"] == "BAMLH0A0HYM2"


def test_fetch_market_data_falls_back_to_freddie_mac_when_fred_fails(monkeypatch):
    monkeypatch.setattr(data_fetcher, "yf", None)
    calls: list[str] = []

    original_read_csv = pd.read_csv

    def fake_read_csv(source):
        if isinstance(source, str) and "fredgraph.csv" in source:
            calls.append(source)
            raise RuntimeError("FRED temporary failure")
        return original_read_csv(source)

    class DummyResponse:
        def __init__(self, payload: str):
            self.payload = payload.encode("utf-8")

        def read(self):
            return self.payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request, timeout=20):
        calls.append(request.full_url)
        return DummyResponse("Date,30YR FRM\n2026-03-05,6.00\n2026-03-12,6.11\n2026-03-19,6.22\n")

    monkeypatch.setattr(data_fetcher.pd, "read_csv", fake_read_csv)
    monkeypatch.setattr(data_fetcher, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        data_fetcher,
        "build_sample_prices",
        lambda: pd.DataFrame({"FRED:MORTGAGE30US": [6.7, 6.75]}, index=pd.date_range("2025-01-03", periods=2, freq="W-FRI")),
    )

    result = data_fetcher.fetch_market_data(
        tickers=["FRED:MORTGAGE30US"],
        period_years=10,
        interval="1wk",
        logger=logging.getLogger("test"),
        use_sample_on_failure=True,
    )

    assert "FRED:MORTGAGE30US" in result.prices.columns
    assert result.acquisition_log[0]["provider"] == "freddie_mac"
    assert result.acquisition_log[0]["status"] == "ok"
    assert any("fredgraph.csv" in url for url in calls)
    assert any("PMMS_history.csv" in url for url in calls)


def test_japan_resident_sample_series_cover_configured_optional_tickers():
    sample = build_sample_prices()

    assert JAPAN_RESIDENT_SAMPLE_TICKERS.issubset(sample.columns)
    assert sample[list(JAPAN_RESIDENT_SAMPLE_TICKERS)].notna().all().all()


def test_sample_only_fetch_uses_japan_resident_sample_series():
    result = data_fetcher.fetch_market_data(
        tickers=sorted(JAPAN_RESIDENT_SAMPLE_TICKERS),
        period_years=10,
        interval="1wk",
        logger=logging.getLogger("test"),
        force_sample=True,
    )

    assert set(result.prices.columns) == JAPAN_RESIDENT_SAMPLE_TICKERS
    assert {entry["status"] for entry in result.acquisition_log} == {"sample_fallback"}
    assert {entry["provider"] for entry in result.acquisition_log} == {"synthetic_sample"}
