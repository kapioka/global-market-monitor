from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from project import risk_engine_v2_official_series as official_series
from project.data_fetcher import FetchResult


def test_official_series_tickers_are_deduped_in_config_order() -> None:
    config = {
        "risk_engine_v2": {
            "official_series": {
                "hy": "FRED:BAMLH0A0HYM2",
                "hy_duplicate": "FRED:BAMLH0A0HYM2",
                "nfci": "FRED:NFCI",
            }
        }
    }

    assert official_series.official_series_tickers(config) == ["FRED:BAMLH0A0HYM2", "FRED:NFCI"]


def test_merge_official_series_preserves_market_columns_and_adds_official() -> None:
    market = pd.DataFrame({"SPY": [100.0, 101.0]}, index=pd.to_datetime(["2026-01-02", "2026-01-09"]))
    official = pd.DataFrame(
        {"FRED:NFCI": [-0.1, -0.2], "SPY": [99.0, 102.0]},
        index=pd.to_datetime(["2026-01-02", "2026-01-16"]),
    )

    merged = official_series.merge_official_series(market, official)

    assert list(merged.index) == [pd.Timestamp("2026-01-02"), pd.Timestamp("2026-01-09"), pd.Timestamp("2026-01-16")]
    assert float(merged.loc[pd.Timestamp("2026-01-02"), "SPY"]) == 99.0
    assert float(merged.loc[pd.Timestamp("2026-01-09"), "SPY"]) == 101.0
    assert float(merged.loc[pd.Timestamp("2026-01-16"), "FRED:NFCI"]) == -0.2


def test_official_series_fetch_writes_diagnostic_store(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.yaml"
    reports_dir = tmp_path / "reports"
    config_path.write_text("placeholder: true\n", encoding="utf-8")
    monkeypatch.setattr(
        official_series,
        "load_config",
        lambda path: {
            "data": {"period_years": 10, "interval": "1wk"},
            "paths": {"cache_dir": "cache"},
            "risk_engine_v2": {"official_series": {"nfci": "FRED:NFCI"}},
        },
    )

    def fake_fetch_market_data(**kwargs):
        assert kwargs["tickers"] == ["FRED:NFCI"]
        assert isinstance(kwargs["logger"], logging.Logger)
        prices = pd.DataFrame({"FRED:NFCI": [0.1]}, index=pd.to_datetime(["2026-01-02"]))
        return FetchResult(prices=prices, warnings=[], source="fred", acquisition_log=[], diagnostics={})

    monkeypatch.setattr(official_series, "fetch_market_data", fake_fetch_market_data)

    result = official_series.run_risk_engine_v2_official_series_fetch(config_path=config_path, reports_dir=reports_dir)

    assert result["status"] == "ok"
    assert (reports_dir / "risk_engine_v2_official_series.csv").exists()
    assert (reports_dir / "risk_engine_v2_official_series.json").exists()


def test_official_series_fetch_retains_history_and_prefers_fetched_overlap(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.yaml"
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    config_path.write_text("placeholder: true\n", encoding="utf-8")
    monkeypatch.setattr(
        official_series,
        "load_config",
        lambda path: {
            "data": {"period_years": 10, "interval": "1wk"},
            "paths": {"cache_dir": "cache"},
            "risk_engine_v2": {"official_series": {"nfci": "FRED:NFCI"}},
        },
    )
    store_path = reports_dir / "risk_engine_v2_official_series.csv"
    pd.DataFrame(
        {"FRED:NFCI": [-0.2, -0.1, -0.05]},
        index=pd.to_datetime(["2025-12-26", "2026-01-02", "2026-01-02"]),
    ).to_csv(store_path)

    def fake_fetch_market_data(**kwargs):
        prices = pd.DataFrame(
            {"FRED:NFCI": [0.1, 0.2]},
            index=pd.to_datetime(["2026-01-02", "2026-01-09"]),
        )
        return FetchResult(prices=prices, warnings=[], source="fred", acquisition_log=[], diagnostics={})

    monkeypatch.setattr(official_series, "fetch_market_data", fake_fetch_market_data)

    result = official_series.run_risk_engine_v2_official_series_fetch(
        config_path=config_path,
        reports_dir=reports_dir,
    )

    stored = official_series.load_official_series_csv(store_path)
    payload = json.loads((reports_dir / "risk_engine_v2_official_series.json").read_text(encoding="utf-8"))
    assert result["status"] == "ok"
    assert list(stored.index) == list(pd.to_datetime(["2025-12-26", "2026-01-02", "2026-01-09"]))
    assert float(stored.loc[pd.Timestamp("2025-12-26"), "FRED:NFCI"]) == -0.2
    assert float(stored.loc[pd.Timestamp("2026-01-02"), "FRED:NFCI"]) == 0.1
    assert payload["history_merge"] == {
        "strategy": "retain_existing_prefer_fetched_on_overlap",
        "existing_store_present": True,
        "existing": {
            "row_count": 2,
            "input_row_count": 3,
            "start_date": "2025-12-26",
            "end_date": "2026-01-02",
            "input_duplicate_date_count": 2,
            "duplicate_date_count": 0,
        },
        "fetched": {
            "row_count": 2,
            "input_row_count": 2,
            "start_date": "2026-01-02",
            "end_date": "2026-01-09",
            "input_duplicate_date_count": 0,
            "duplicate_date_count": 0,
        },
        "merged": {
            "row_count": 3,
            "input_row_count": 3,
            "start_date": "2025-12-26",
            "end_date": "2026-01-09",
            "input_duplicate_date_count": 0,
            "duplicate_date_count": 0,
        },
        "overlap_date_count": 1,
    }


def test_official_series_fetch_does_not_overwrite_malformed_existing_store(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.yaml"
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    config_path.write_text("placeholder: true\n", encoding="utf-8")
    monkeypatch.setattr(
        official_series,
        "load_config",
        lambda path: {
            "data": {"period_years": 10, "interval": "1wk"},
            "paths": {"cache_dir": "cache"},
            "risk_engine_v2": {"official_series": {"nfci": "FRED:NFCI"}},
        },
    )
    store_path = reports_dir / "risk_engine_v2_official_series.csv"
    original = "date,FRED:NFCI\nnot-a-date,broken\n"
    store_path.write_text(original, encoding="utf-8")

    def fake_fetch_market_data(**kwargs):
        prices = pd.DataFrame({"FRED:NFCI": [0.1]}, index=pd.to_datetime(["2026-01-02"]))
        return FetchResult(prices=prices, warnings=[], source="fred", acquisition_log=[], diagnostics={})

    monkeypatch.setattr(official_series, "fetch_market_data", fake_fetch_market_data)

    try:
        official_series.run_risk_engine_v2_official_series_fetch(
            config_path=config_path,
            reports_dir=reports_dir,
        )
    except ValueError as error:
        assert "contains invalid dates" in str(error)
    else:
        raise AssertionError("malformed existing store must fail")

    assert store_path.read_text(encoding="utf-8") == original
    assert not (reports_dir / "risk_engine_v2_official_series.json").exists()
