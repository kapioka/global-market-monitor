from __future__ import annotations

import pandas as pd

from project.risk_line_reality_check import build_reality_checked_thresholds


def test_build_reality_checked_thresholds_demotes_low_precision_extreme():
    index = pd.date_range("2024-01-05", periods=10, freq="W-FRI")
    prices = pd.DataFrame(
        {
            "SPY": [100, 99, 98, 94, 93, 92, 91, 90, 89, 88],
            "HYG": [100, 100, 99.8, 99.5, 99.2, 99.0, 98.9, 98.8, 98.7, 98.6],
            "LQD": [100, 100.1, 100.2, 100.3, 100.4, 100.5, 100.6, 100.7, 100.8, 100.9],
            "^VIX": [18, 19, 20, 25, 30, 35, 40, 38, 34, 30],
            "^MOVE": [90, 91, 92, 94, 96, 98, 100, 99, 97, 96],
            "CL=F": [70, 71, 72, 73, 74, 75, 76, 75, 74, 73],
            "BZ=F": [75, 76, 77, 78, 79, 80, 81, 80, 79, 78],
            "DX-Y.NYB": [100, 100.2, 100.4, 100.5, 100.6, 100.7, 100.8, 100.9, 101.0, 101.1],
            "^TNX": [3.8, 3.85, 3.9, 3.95, 4.0, 4.05, 4.1, 4.08, 4.06, 4.04],
        },
        index=index,
        dtype=float,
    )
    backtest = {
        "targets": ["extreme_target"],
        "indicators": {
            "SPY": {
                "family": "price_shock",
                "adverse_direction": "lower",
                "targets": {
                    "extreme_target": {
                        "best": {"feature": "roc_8w", "threshold": -0.03, "quantile": 0.1, "f1": 0.3, "precision": 0.2, "recall": 0.6, "false_positive_rate": 0.08},
                        "top_candidates": [
                            {"feature": "roc_8w", "threshold": -0.03, "quantile": 0.1, "f1": 0.3, "precision": 0.2, "recall": 0.6, "false_positive_rate": 0.08},
                        ],
                    }
                },
            }
        },
    }

    report = build_reality_checked_thresholds(prices, backtest)
    summary = report["indicators"]["SPY"]["targets"]["extreme_target"]

    assert summary["decision"] == "fallback_review"
    assert summary["coverage_forced"] is True
    assert summary["actual_value_check"]["reasons"]
