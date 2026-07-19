from __future__ import annotations

import pandas as pd

from project.risk_feature_contract import build_point_in_time_feature_contract, normalize_observation_series


def test_daily_point_in_time_returns_use_5_20_60_business_sessions():
    index = pd.bdate_range("2026-01-01", periods=70)
    series = pd.Series([100.0 + i for i in range(70)], index=index)

    payload = build_point_in_time_feature_contract(
        series,
        symbol="SPY",
        evaluation_date=index[-1],
        source_kind="yfinance",
        price_type="adjusted_close",
        minimum_history=61,
    )

    features = payload["features"]
    assert features["return_1w"] == (169.0 / 164.0) - 1.0
    assert features["return_4w"] == (169.0 / 149.0) - 1.0
    assert features["return_12w"] == (169.0 / 109.0) - 1.0
    assert payload["metadata"]["stage_eligible"] is True
    assert payload["metadata"]["comparison_observation_dates"]["return_1w"] == index[-6].date().isoformat()


def test_missing_business_days_use_latest_available_as_of_comparison_date():
    index = pd.bdate_range("2026-01-01", periods=30).delete(-6)
    series = pd.Series([100.0 + i for i in range(len(index))], index=index)

    payload = build_point_in_time_feature_contract(
        series,
        symbol="SPY",
        evaluation_date=index[-1],
        source_kind="yfinance",
        price_type="adjusted_close",
        minimum_history=10,
    )

    comparison = payload["comparisons"]["return_1w"]
    assert comparison["status"] == "valid"
    assert comparison["observation_date"] < comparison["target_comparison_date"]
    assert payload["features"]["return_1w"] is not None


def test_weekly_series_does_not_compare_same_observation_to_itself():
    index = pd.date_range("2026-01-02", periods=8, freq="W-FRI")
    series = pd.Series([100.0 + i for i in range(8)], index=index)

    payload = build_point_in_time_feature_contract(
        series,
        symbol="FRED:TEST",
        evaluation_date="2026-02-27",
        source_kind="fred",
        price_type="yield",
        minimum_history=2,
    )

    assert payload["metadata"]["frequency"] == "weekly"
    assert payload["comparisons"]["return_1w"]["status"] == "same_observation_comparison"
    assert payload["features"]["return_1w"] is None
    assert "same_observation_comparison" in payload["metadata"]["quality_flags"]


def test_insufficient_history_returns_none_instead_of_zero():
    index = pd.bdate_range("2026-01-01", periods=4)
    series = pd.Series([100.0, 101.0, 102.0, 103.0], index=index)

    payload = build_point_in_time_feature_contract(
        series,
        symbol="SPY",
        evaluation_date=index[-1],
        source_kind="yfinance",
        price_type="adjusted_close",
        minimum_history=61,
    )

    assert payload["features"]["return_1w"] is None
    assert "insufficient_history" in payload["metadata"]["quality_flags"]
    assert payload["metadata"]["stage_eligible"] is False


def test_genuine_zero_return_is_preserved():
    index = pd.bdate_range("2026-01-01", periods=70)
    series = pd.Series([100.0 for _ in range(70)], index=index)

    payload = build_point_in_time_feature_contract(
        series,
        symbol="SPY",
        evaluation_date=index[-1],
        source_kind="yfinance",
        price_type="adjusted_close",
        minimum_history=61,
    )

    assert payload["features"]["return_1w"] == 0.0
    assert payload["features"]["return_4w"] == 0.0
    assert payload["features"]["return_12w"] == 0.0
    assert "comparison_unavailable" not in payload["metadata"]["quality_flags"]


def test_future_observations_are_excluded_and_flagged():
    index = pd.bdate_range("2026-01-01", periods=70)
    series = pd.Series([100.0 + i for i in range(70)], index=index)

    payload = build_point_in_time_feature_contract(
        series,
        symbol="SPY",
        evaluation_date=index[-5],
        source_kind="yfinance",
        price_type="adjusted_close",
        minimum_history=61,
    )

    assert payload["metadata"]["latest_observation_date"] == index[-5].date().isoformat()
    assert "future_observation_excluded" in payload["metadata"]["quality_flags"]
    assert payload["features"]["current"] == float(series.loc[index[-5]])


def test_duplicate_dates_keep_last_observation():
    index = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-02", "2026-01-05"])
    series = pd.Series([100.0, 101.0, 111.0, 112.0], index=index)

    normalized = normalize_observation_series(series)

    assert len(normalized) == 3
    assert normalized.loc[pd.Timestamp("2026-01-02")] == 111.0


def test_timezone_dates_are_normalized_to_date_boundaries():
    index = pd.to_datetime(["2026-01-01 23:00:00+09:00", "2026-01-02 23:00:00+09:00"])
    series = pd.Series([100.0, 101.0], index=index)

    normalized = normalize_observation_series(series)

    assert list(normalized.index) == [pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-02")]


def test_empty_dated_series_keeps_datetime_index_for_unavailable_contract():
    series = pd.Series([], index=pd.to_datetime([]), dtype=float)

    payload = build_point_in_time_feature_contract(
        series,
        symbol="FRED:BAMLH0A0HYM2",
        evaluation_date="2018-01-05",
        source_kind="fred",
        price_type="yield",
        minimum_history=52,
    )

    assert payload["metadata"]["freshness_status"] == "unknown"
    assert payload["metadata"]["quality_flags"] == ["source_unavailable"]


def test_stale_series_is_not_stage_eligible():
    index = pd.bdate_range("2026-01-01", periods=70)
    series = pd.Series([100.0 + i for i in range(70)], index=index)

    payload = build_point_in_time_feature_contract(
        series,
        symbol="SPY",
        evaluation_date=index[-1] + pd.Timedelta(days=20),
        source_kind="yfinance",
        price_type="adjusted_close",
        minimum_history=61,
    )

    assert payload["metadata"]["freshness_status"] == "stale"
    assert "stale" in payload["metadata"]["quality_flags"]
    assert payload["metadata"]["stage_eligible"] is False


def test_volatility_index_jump_is_not_misclassified_as_data_discontinuity():
    index = pd.bdate_range("2025-01-01", periods=70)
    values = [15.0 + (i % 4) for i in range(70)]
    values[-2:] = [16.0, 40.0]
    for symbol in ("^VIX", "^MOVE"):
        payload = build_point_in_time_feature_contract(
            pd.Series(values, index=index),
            symbol=symbol,
            evaluation_date=index[-1],
            source_kind="yfinance",
            price_type="index",
            minimum_history=61,
        )

        assert "suspicious_discontinuity" not in payload["metadata"]["quality_flags"]
        assert payload["metadata"]["stage_eligible"] is True


def test_equity_jump_still_triggers_discontinuity_guard():
    index = pd.bdate_range("2025-01-01", periods=70)
    values = [100.0 + i for i in range(69)] + [80.0]

    payload = build_point_in_time_feature_contract(
        pd.Series(values, index=index),
        symbol="SPY",
        evaluation_date=index[-1],
        source_kind="yfinance",
        price_type="adjusted_close",
        minimum_history=61,
    )

    assert "suspicious_discontinuity" in payload["metadata"]["quality_flags"]
    assert payload["metadata"]["stage_eligible"] is False
