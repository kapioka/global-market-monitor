from __future__ import annotations

import pandas as pd

from project.inflation_monitor import build_inflation_monitor


def test_build_inflation_monitor_assigns_expected_signals():
    prices = pd.DataFrame(
        {
            "CL=F": [100.0, 102.0, 105.0, 109.0, 115.0],
            "GC=F": [100.0, 101.0, 102.0, 104.0, 107.0],
            "DX-Y.NYB": [100.0, 100.5, 101.3, 102.8, 105.0],
            "ZW=F": [100.0, 101.5, 103.0, 107.0, 111.5],
            "ZC=F": [100.0, 100.8, 101.9, 104.0, 107.5],
            "FRED:MORTGAGE30US": [6.0, 6.05, 6.1, 6.25, 6.45],
            "^TNX": [100.0, 100.3, 101.2, 103.7, 106.0],
        }
    )

    rows = build_inflation_monitor(
        prices,
        inflation_map={"Oil": "CL=F", "Gold": "GC=F", "Dollar_Index": "DX-Y.NYB", "Wheat": "ZW=F", "Corn": "ZC=F", "Mortgage_30Y": "FRED:MORTGAGE30US", "US10Y": "^TNX"},
        windows={"short": 1, "medium": 2, "long": 4},
        zscore_window=5,
    )

    by_ticker = {row["ticker"]: row for row in rows}
    assert by_ticker["CL=F"]["signal_label"] == "インフレ圧力上昇"
    assert by_ticker["DX-Y.NYB"]["signal_label"] == "ドル高進行"
    assert by_ticker["ZW=F"]["signal_label"] == "食品価格上昇圧力"
    assert by_ticker["FRED:MORTGAGE30US"]["signal_label"] == "住宅ローン負担上昇"
