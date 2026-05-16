from __future__ import annotations

import pandas as pd

from project.risk_line_backtest import BacktestConfig, build_risk_line_backtest_report


def test_build_risk_line_backtest_report_returns_ranked_candidates_for_all_ten_indicators():
    index = pd.date_range("2019-01-04", periods=180, freq="W-FRI")
    prices = pd.DataFrame(
        {
            "SPY": [100.0 + i * 0.25 for i in range(180)],
            "HYG": [80.0 + i * 0.05 for i in range(180)],
            "LQD": [100.0 + i * 0.02 for i in range(180)],
            "^VIX": [17.0 + (i % 9) * 0.5 for i in range(180)],
            "^MOVE": [105.0 + (i % 7) * 1.5 for i in range(180)],
            "CL=F": [68.0 + i * 0.18 for i in range(180)],
            "BZ=F": [72.0 + i * 0.2 for i in range(180)],
            "DX-Y.NYB": [95.0 + i * 0.04 for i in range(180)],
            "^TNX": [2.1 + i * 0.01 for i in range(180)],
        },
        index=index,
        dtype=float,
    )
    prices.loc[index[120:125], "SPY"] = [126.0, 119.0, 114.0, 113.0, 112.0]
    prices.loc[index[120:125], "HYG"] = [86.0, 84.5, 83.8, 83.0, 82.6]
    prices.loc[index[120:125], "LQD"] = [102.4, 102.3, 102.2, 102.1, 102.0]
    prices.loc[index[120:125], "^VIX"] = [24.0, 31.0, 39.0, 47.0, 42.0]
    prices.loc[index[120:125], "^MOVE"] = [112.0, 121.0, 132.0, 145.0, 138.0]
    prices.loc[index[120:125], "CL=F"] = [80.0, 88.0, 97.0, 108.0, 110.0]
    prices.loc[index[120:125], "BZ=F"] = [84.0, 92.0, 101.0, 112.0, 114.0]
    prices.loc[index[120:125], "DX-Y.NYB"] = [99.0, 101.0, 103.2, 105.0, 104.4]
    prices.loc[index[120:125], "^TNX"] = [3.1, 3.25, 3.45, 3.6, 3.55]

    report = build_risk_line_backtest_report(
        prices,
        backtest_config=BacktestConfig(
            min_observations=20,
            walk_forward_train_size=60,
            walk_forward_test_size=20,
            walk_forward_step_size=20,
        ),
    )

    assert report["indicator_count"] == 10
    for ticker in ["SPY", "HYG", "LQD", "HYG/LQD", "^VIX", "^MOVE", "CL=F", "BZ=F", "DX-Y.NYB", "^TNX"]:
        warning_target = report["indicators"][ticker]["targets"]["warning_target"]
        assert warning_target["candidate_count"] > 0
        assert warning_target["best"] is not None
    assert report["indicators"]["^MOVE"]["targets"]["danger_target"]["best"] is not None
    assert report["indicators"]["CL=F"]["targets"]["warning_target"]["walk_forward"]["window_count"] >= 1
