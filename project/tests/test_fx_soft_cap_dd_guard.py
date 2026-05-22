from __future__ import annotations

from project.fx_soft_cap_dd_guard import evaluate_all_dd_guards, evaluate_dd_guard


def test_combined_dd_guard_blocks_weak_relative_trend_and_fx_headwind() -> None:
    case = {
        "current_final_action": "watch",
        "fx_flags": ["foreign_asset_fx_headwind"],
        "feature_snapshot": {
            "acwi_spy_relative_13w": -0.02,
            "vix_level": 16.0,
            "vix_change_4w": 0.02,
            "hyg_lqd_ratio_return_4w": 0.0,
            "acwi_drawdown_13w": -0.01,
            "acwi_return_4w": 0.02,
            "acwi_return_13w": 0.04,
        },
    }

    result = evaluate_dd_guard(case, "combined_dd_guard")

    assert result["passes"] is False
    assert "equity_trend_ok" in result["blocked_reasons"]
    assert "fx_headwind_ok" in result["blocked_reasons"]


def test_dd_guards_allow_clean_context() -> None:
    case = {
        "current_final_action": "watch",
        "fx_flags": ["japan_fx_risk_caution"],
        "feature_snapshot": {
            "acwi_spy_relative_13w": 0.01,
            "vix_level": 16.0,
            "vix_change_4w": 0.02,
            "hyg_lqd_ratio_return_4w": 0.01,
            "acwi_drawdown_13w": 0.0,
            "acwi_return_4w": 0.02,
            "acwi_return_13w": 0.05,
        },
    }

    result = evaluate_dd_guard(case, "combined_dd_guard")

    assert result["passes"] is True
    assert result["action"] == "buy_candidate"
    assert set(evaluate_all_dd_guards(case)) == {
        "equity_trend_guard",
        "volatility_guard",
        "credit_guard",
        "drawdown_context_guard",
        "combined_dd_guard",
    }
