from __future__ import annotations

from pathlib import Path

import pandas as pd

from project.regime_aware_fx_policy_replay import build_regime_aware_fx_policy_replay, run_regime_aware_fx_policy_replay


def test_regime_aware_replay_compares_candidates(tmp_path: Path) -> None:
    path = _features_csv(tmp_path)

    payload = build_regime_aware_fx_policy_replay(path)

    assert payload["status"] == "ok"
    assert payload["adoption_decision"] == "hold"
    assert any(row["candidate"] == "regime_aware_with_dd_guard" for row in payload["candidates"])
    assert payload["regime_breakdown"]


def test_regime_aware_replay_writes_reports(tmp_path: Path) -> None:
    path = _features_csv(tmp_path)

    result = run_regime_aware_fx_policy_replay(path, tmp_path)

    assert result["status"] == "ok"
    assert (tmp_path / "regime_aware_fx_policy_replay.json").exists()
    assert (tmp_path / "regime_aware_fx_policy_replay.md").exists()


def _features_csv(tmp_path: Path) -> Path:
    dates = pd.date_range("2020-01-03", periods=40, freq="W-FRI")
    frame = pd.DataFrame(
        {
            "price_acwi": [100 + index for index in range(40)],
            "price_spy": [100 + index * 0.9 for index in range(40)],
            "acwi_return_4w": [0.04] * 40,
            "acwi_return_13w": [0.08] * 40,
            "spy_return_13w": [0.06] * 40,
            "acwi_drawdown_13w": [0.0] * 40,
            "usdjpy_change_4w": [0.03] * 40,
            "usdjpy_change_13w": [0.05] * 40,
            "vix_level": [16.0] * 40,
            "vix_change_4w": [0.01] * 40,
            "hyg_lqd_ratio_return_4w": [0.01] * 40,
            "acwi_spy_relative_13w": [0.01] * 40,
        },
        index=dates,
    )
    frame.index.name = "date"
    path = tmp_path / "features.csv"
    frame.to_csv(path)
    return path
