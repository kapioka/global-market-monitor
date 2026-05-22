from __future__ import annotations

from project.fx_soft_cap_balanced_guard import build_fx_soft_cap_balanced_guard, evaluate_balanced_dd_guard


def test_balanced_guard_blocks_headwind_with_underperformance() -> None:
    case = {
        "current_final_action": "watch",
        "fx_flags": ["foreign_asset_fx_headwind"],
        "feature_snapshot": {
            "acwi_spy_relative_13w": -0.02,
            "vix_level": 16.0,
            "vix_change_4w": 0.01,
            "hyg_lqd_ratio_return_4w": 0.01,
            "acwi_drawdown_13w": 0.0,
            "acwi_return_4w": 0.03,
            "acwi_return_13w": 0.1,
        },
    }

    result = evaluate_balanced_dd_guard(case)

    assert result["passes"] is False
    assert "headwind_not_with_underperformance" in result["blocked_reasons"]


def test_balanced_guard_allows_mild_non_headwind_underperformance() -> None:
    case = {
        "current_final_action": "watch",
        "fx_flags": ["japan_fx_risk_caution"],
        "feature_snapshot": {
            "acwi_spy_relative_13w": -0.02,
            "vix_level": 16.0,
            "vix_change_4w": 0.01,
            "hyg_lqd_ratio_return_4w": 0.01,
            "acwi_drawdown_13w": 0.0,
            "acwi_return_4w": 0.03,
            "acwi_return_13w": 0.1,
        },
    }

    assert evaluate_balanced_dd_guard(case)["passes"] is True


def test_balanced_guard_report_compares_candidates() -> None:
    replay = {
        "cases": [
            {
                "classification": "overblocked_by_current",
                "current_final_action": "watch",
                "fx_flags": ["japan_fx_risk_caution"],
                "feature_snapshot": {
                    "acwi_spy_relative_13w": -0.02,
                    "vix_level": 16.0,
                    "vix_change_4w": 0.01,
                    "hyg_lqd_ratio_return_4w": 0.01,
                    "acwi_drawdown_13w": 0.0,
                    "acwi_return_4w": 0.03,
                    "acwi_return_13w": 0.1,
                },
                "forward_returns": {"13w": 0.05},
                "excess_returns": {"13w": 0.01},
                "max_drawdowns": {"13w": -0.03},
            }
        ]
    }

    payload = build_fx_soft_cap_balanced_guard(replay)

    assert payload["status"] == "ok"
    assert payload["candidates"][-1]["candidate"] == "balanced_dd_guard"
