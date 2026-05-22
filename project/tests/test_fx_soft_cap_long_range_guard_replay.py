from __future__ import annotations

from pathlib import Path

import pandas as pd

from project.fx_soft_cap_long_range_guard_replay import build_fx_soft_cap_long_range_guard_replay, run_fx_soft_cap_long_range_guard_replay


def test_long_range_guard_replay_compares_without_equity_trend(tmp_path: Path) -> None:
    dates = pd.date_range("2020-01-03", periods=40, freq="W-FRI")
    frame = pd.DataFrame(
        {
            "price_acwi": [100 + index for index in range(40)],
            "price_spy": [100 + index * 0.8 for index in range(40)],
            "acwi_return_4w": [0.04] * 40,
            "acwi_return_13w": [0.08] * 40,
            "acwi_drawdown_13w": [0.0] * 40,
            "usdjpy_change_4w": [0.03] * 40,
            "usdjpy_change_13w": [0.05] * 40,
            "vix_level": [18.0] * 40,
            "vix_change_4w": [0.01] * 40,
            "hyg_lqd_ratio_return_4w": [0.01] * 40,
            "acwi_spy_relative_13w": [-0.02] * 40,
        },
        index=dates,
    )
    path = tmp_path / "features.csv"
    frame.index.name = "date"
    frame.to_csv(path)

    payload = build_fx_soft_cap_long_range_guard_replay(path)

    assert payload["status"] == "ok"
    assert payload["replay_start"] == "2020-01-03"
    assert payload["usable_weeks"] == 40
    assert any(row["candidate"] == "without_equity_trend_guard" for row in payload["candidates"])
    assert "2020_crash_recovery" in payload["regime_breakdown"]


def test_long_range_guard_replay_writes_reports(tmp_path: Path) -> None:
    dates = pd.date_range("2024-01-05", periods=32, freq="W-FRI")
    frame = pd.DataFrame(
        {
            "price_acwi": [100 + index for index in range(32)],
            "price_spy": [100 + index for index in range(32)],
            "acwi_return_4w": [0.04] * 32,
            "acwi_return_13w": [0.08] * 32,
            "acwi_drawdown_13w": [0.0] * 32,
            "usdjpy_change_4w": [0.03] * 32,
            "usdjpy_change_13w": [0.05] * 32,
            "vix_level": [18.0] * 32,
        },
        index=dates,
    )
    path = tmp_path / "features.csv"
    frame.index.name = "date"
    frame.to_csv(path)

    result = run_fx_soft_cap_long_range_guard_replay(path, tmp_path)

    assert result["status"] == "ok"
    assert (tmp_path / "fx_soft_cap_long_range_guard_replay.json").exists()
    assert (tmp_path / "fx_soft_cap_long_range_guard_replay.md").exists()
