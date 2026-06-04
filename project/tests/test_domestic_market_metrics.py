from __future__ import annotations

import pandas as pd

from project.domestic_market_metrics import build_domestic_market_metrics


def _prices() -> pd.DataFrame:
    index = pd.date_range("2026-01-02", periods=16, freq="W-FRI")
    return pd.DataFrame(
        {
            "1306.T": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 108, 107, 106, 105, 104, 103],
            "1321.T": [100 + i for i in range(16)],
            "EWJ": [80 + i * 0.5 for i in range(16)],
            "2510.T": [100, 100, 100, 100, 99, 98, 97, 96, 95, 95, 94, 94, 93, 92, 91, 90],
            "1343.T": [100, 102, 104, 106, 108, 110, 108, 106, 104, 102, 100, 98, 96, 94, 92, 90],
            "1540.T": [100, 100, 101, 100, 102, 103, 102, 104, 105, 104, 106, 107, 108, 109, 110, 111],
            "USDJPY=X": [140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155],
            "EURJPY=X": [160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175],
            "GLD": [180 + i for i in range(16)],
            "GC=F": [1900 + i * 3 for i in range(16)],
            "AGG": [100 - i * 0.2 for i in range(16)],
        },
        index=index,
        dtype=float,
    )


def test_build_domestic_market_metrics_calculates_target_series() -> None:
    payload = build_domestic_market_metrics(_prices(), acquisition_log=[{"requested_ticker": "1306.T", "status": "ok"}])
    by_symbol = payload["by_symbol"]

    assert payload["affects_final_action"] is False
    assert payload["affects_buy_readiness_score"] is False
    assert by_symbol["1306.T"]["asset_group"] == "jp_equity"
    assert by_symbol["1306.T"]["current_value"] == 103.0
    assert by_symbol["1306.T"]["change_4w"] < 0
    assert by_symbol["1306.T"]["change_12w"] is not None
    assert by_symbol["1306.T"]["max_drawdown"] is not None
    assert by_symbol["1306.T"]["trend_label"] in {"flat", "weakening", "falling"}


def test_domestic_market_metrics_keep_jpy_gold_separate_from_usd_gold() -> None:
    by_symbol = build_domestic_market_metrics(_prices())["by_symbol"]

    assert by_symbol["1540.T"]["asset_group"] == "gold_jpy"
    assert by_symbol["GLD"]["asset_group"] == "gold_usd"
    assert by_symbol["GC=F"]["asset_group"] == "gold_usd"


def test_domestic_market_metrics_mark_missing_partial_and_sample() -> None:
    short_prices = _prices().tail(4).drop(columns=["1343.T"])
    payload = build_domestic_market_metrics(
        short_prices,
        acquisition_log=[
            {"requested_ticker": "2510.T", "used_ticker": "2510.T", "status": "sample_fallback", "source": "sample"},
            {"requested_ticker": "1343.T", "status": "unavailable"},
        ],
    )
    by_symbol = payload["by_symbol"]

    assert by_symbol["2510.T"]["is_sample"] is True
    assert by_symbol["2510.T"]["data_quality"] == "sample"
    assert "insufficient_history" in by_symbol["2510.T"]["limitations"]
    assert by_symbol["1343.T"]["is_available"] is False
    assert by_symbol["1343.T"]["data_quality"] == "unavailable"
    assert "missing_series" in by_symbol["1343.T"]["limitations"]


def test_fx_metrics_use_usdjpy_and_eurjpy_without_dxy_substitution() -> None:
    by_symbol = build_domestic_market_metrics(_prices())["by_symbol"]

    assert by_symbol["USDJPY=X"]["asset_group"] == "fx"
    assert by_symbol["EURJPY=X"]["asset_group"] == "fx"
    assert "DX-Y.NYB" not in by_symbol
