from __future__ import annotations

from pathlib import Path

import pandas as pd

from project.historical_feature_builder import build_historical_features, run_historical_feature_builder


def test_historical_feature_builder_creates_weekly_features(tmp_path: Path) -> None:
    dates = pd.date_range("2026-01-02", periods=30, freq="W-FRI")
    prices = pd.DataFrame(
        {
            "ACWI": [100.0 + index for index in range(30)],
            "SPY": [100.0 + index * 0.8 for index in range(30)],
            "HYG": [80.0 + index * 0.2 for index in range(30)],
            "LQD": [90.0 + index * 0.1 for index in range(30)],
            "USDJPY=X": [150.0 - index * 0.3 for index in range(30)],
        },
        index=dates,
    )

    payload = build_historical_features(prices)

    assert payload["summary"]["row_count"] == 30
    assert "acwi_return_13w" in payload["features"].columns
    assert "hyg_lqd_ratio" in payload["features"].columns
    assert "usdjpy_change_4w" in payload["features"].columns


def test_historical_feature_builder_cli_runner_writes_csv(tmp_path: Path) -> None:
    prices = pd.DataFrame({"date": pd.date_range("2026-01-02", periods=6, freq="W-FRI"), "ACWI": [100, 101, 102, 103, 104, 105]})
    input_path = tmp_path / "prices.csv"
    output_path = tmp_path / "features.csv"
    prices.to_csv(input_path, index=False)

    summary = run_historical_feature_builder(input_path, output_path, tmp_path)

    assert summary["status"] == "ok"
    assert output_path.exists()
    assert (tmp_path / "historical_feature_summary.json").exists()
