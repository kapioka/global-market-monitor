from __future__ import annotations

from pathlib import Path

import pandas as pd

from project.fx_soft_cap_historical_replay import (
    build_fx_soft_cap_historical_replay,
    render_fx_soft_cap_historical_replay_markdown,
    run_fx_soft_cap_historical_replay,
)


def test_fx_soft_cap_historical_replay_classifies_overblocked_case(tmp_path: Path) -> None:
    dates = pd.date_range("2025-01-03", periods=45, freq="W-FRI")
    features = pd.DataFrame(index=dates)
    features["price_acwi"] = [100.0 + index for index in range(45)]
    features["price_spy"] = [100.0 + index * 0.5 for index in range(45)]
    features["acwi_return_4w"] = 0.04
    features["acwi_return_13w"] = 0.06
    features["acwi_drawdown_13w"] = 0.0
    features["usdjpy_change_4w"] = -0.03
    features["usdjpy_change_13w"] = -0.05
    features["vix_level"] = 18.0

    payload = build_fx_soft_cap_historical_replay(features)

    assert payload["fx_soft_cap_buy_candidate_count"] > 0
    assert payload["current_watch_to_fx_soft_cap_buy_candidate_count"] > 0
    assert payload["classification_counts"]["overblocked_by_current"] > 0
    assert "historical replay" in render_fx_soft_cap_historical_replay_markdown(payload)


def test_fx_soft_cap_historical_replay_runner_writes_reports(tmp_path: Path) -> None:
    dates = pd.date_range("2025-01-03", periods=20, freq="W-FRI")
    features = pd.DataFrame(
        {
            "date": dates,
            "price_acwi": [100.0 + index for index in range(20)],
            "price_spy": [100.0 + index for index in range(20)],
            "acwi_return_4w": [0.04] * 20,
            "acwi_return_13w": [0.06] * 20,
            "acwi_drawdown_13w": [0.0] * 20,
            "usdjpy_change_4w": [-0.03] * 20,
            "usdjpy_change_13w": [-0.05] * 20,
            "vix_level": [18.0] * 20,
        }
    )
    feature_path = tmp_path / "features.csv"
    features.to_csv(feature_path, index=False)

    summary = run_fx_soft_cap_historical_replay(feature_path, tmp_path)

    assert summary["status"] == "ok"
    assert (tmp_path / "fx_soft_cap_historical_replay.json").exists()
    assert (tmp_path / "fx_soft_cap_historical_replay.md").exists()
