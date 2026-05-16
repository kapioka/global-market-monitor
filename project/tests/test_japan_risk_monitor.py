from __future__ import annotations

import pandas as pd

from project.japan_risk_monitor import build_japan_risk_monitor


def test_japan_risk_monitor_converts_foreign_assets_to_jpy_terms():
    index = pd.date_range("2025-01-03", periods=20, freq="W-FRI")
    prices = pd.DataFrame(
        {
            "SPY": [100 + i for i in range(20)],
            "GLD": [80 + i * 0.2 for i in range(20)],
            "USDJPY=X": [140 + i * 0.6 for i in range(20)],
        },
        index=index,
        dtype=float,
    )

    result = build_japan_risk_monitor(
        prices,
        {"US_Stocks": "SPY", "Gold": "GLD"},
        {"usd_jpy": "USDJPY=X"},
        {"short": 1, "medium": 4, "long": 12},
        10,
    )

    assert result["available"] is True
    assert result["usd_jpy"]["ticker"] == "USDJPY=X"
    assert result["foreign_assets"]
    assert result["foreign_assets"][0]["jpy_return_4w"] is not None
    assert "USDJPY" in result["summary"]


def test_japan_risk_monitor_flags_yen_weakness_and_fx_dependency():
    index = pd.date_range("2025-01-03", periods=20, freq="W-FRI")
    prices = pd.DataFrame(
        {
            "SPY": [100.0 for _ in range(20)],
            "USDJPY=X": [130.0 + i * 1.5 for i in range(20)],
        },
        index=index,
    )

    result = build_japan_risk_monitor(
        prices,
        {"US_Stocks": "SPY"},
        {"usd_jpy": "USDJPY=X"},
        {"short": 1, "medium": 4, "long": 12},
        10,
        settings={"yen_shock_4w": 0.03, "fx_dependency_ratio": 0.5},
    )

    assert result["usd_jpy"]["signal_label"] in {"円安急進", "円安進行"}
    assert "yen_weakness" in result["flags"]
    assert "foreign_asset_fx_dependency" in result["flags"]
    assert result["level"] in {"moderate", "high"}


def test_japan_risk_monitor_returns_unavailable_without_usdjpy():
    result = build_japan_risk_monitor(
        pd.DataFrame({"SPY": [100.0, 101.0]}),
        {"US_Stocks": "SPY"},
        {"usd_jpy": "USDJPY=X"},
        {"short": 1, "medium": 4, "long": 12},
        10,
    )

    assert result["available"] is False
    assert result["level"] == "unknown"
