from __future__ import annotations

import pandas as pd

from project.credit_monitor import build_credit_monitor


def test_build_credit_monitor_includes_ratio_row():
    prices = pd.DataFrame(
        {
            "HYG": [80.0, 81.0, 82.0, 81.0, 83.0],
            "LQD": [100.0, 100.5, 101.0, 101.5, 102.0],
        }
    )

    rows = build_credit_monitor(
        prices,
        credit_map={"HYG": "HYG", "LQD": "LQD"},
        windows={"short": 1, "medium": 2, "long": 4},
        zscore_window=5,
    )

    tickers = [row["ticker"] for row in rows]
    assert "HYG" in tickers
    assert "LQD" in tickers
    assert "HYG/LQD" in tickers


def test_build_credit_monitor_sets_credit_stress_label_for_weak_ratio():
    prices = pd.DataFrame(
        {
            "HYG": [100.0, 99.0, 98.0, 96.0, 94.0],
            "LQD": [100.0, 100.5, 101.0, 101.2, 101.5],
        }
    )

    rows = build_credit_monitor(
        prices,
        credit_map={"HYG": "HYG", "LQD": "LQD"},
        windows={"short": 1, "medium": 2, "long": 4},
        zscore_window=5,
    )

    ratio_row = next(row for row in rows if row["ticker"] == "HYG/LQD")
    assert ratio_row["signal_label"] == "信用収縮警戒"
