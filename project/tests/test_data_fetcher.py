from __future__ import annotations

import logging
import pandas as pd

import project.data_fetcher as data_fetcher


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

    def fake_read_csv(url: str):
        assert "MORTGAGE30US" in url
        return pd.DataFrame(
            {
                "DATE": ["2026-01-02", "2026-01-09", "2026-01-16"],
                "MORTGAGE30US": [6.91, 6.88, 6.84],
            }
        )

    monkeypatch.setattr(data_fetcher.pd, "read_csv", fake_read_csv)
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
