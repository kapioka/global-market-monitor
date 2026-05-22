from __future__ import annotations

from project.fx_soft_cap_drawdown_analysis import build_fx_soft_cap_drawdown_analysis, render_fx_soft_cap_drawdown_analysis_markdown


def test_drawdown_analysis_identifies_worst_case() -> None:
    replay = {
        "cases": [
            {
                "date": "2025-01-31",
                "classification": "correctly_blocked",
                "risk_stage": "normal",
                "reliability_level": "historical_price_replay",
                "market_raw_action": "buy_candidate",
                "current_final_action": "watch",
                "fx_soft_cap_action": "buy_candidate",
                "fx_flags": ["foreign_asset_fx_headwind"],
                "feature_snapshot": {"acwi_spy_relative_13w": -0.02, "vix_change_4w": 0.2},
                "forward_returns": {"13w": -0.01},
                "excess_returns": {"13w": 0.01},
                "max_drawdowns": {"13w": -0.142534},
            },
            {
                "date": "2025-02-07",
                "classification": "overblocked_by_current",
                "risk_stage": "normal",
                "reliability_level": "historical_price_replay",
                "fx_flags": ["japan_fx_risk_caution"],
                "feature_snapshot": {"acwi_spy_relative_13w": 0.01},
                "forward_returns": {"13w": 0.05},
                "excess_returns": {"13w": 0.02},
                "max_drawdowns": {"13w": -0.03},
            },
        ]
    }

    payload = build_fx_soft_cap_drawdown_analysis(replay)

    assert payload["worst_case"]["generated_at"] == "2025-01-31"
    assert payload["worst_case"]["max_drawdown_13w"] == -0.142534
    assert "ACWI underperformed SPY" in payload["worst_case"]["reason_summary"]
    assert "drawdown analysis" in render_fx_soft_cap_drawdown_analysis_markdown(payload)
