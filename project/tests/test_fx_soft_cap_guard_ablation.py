from __future__ import annotations

from project.fx_soft_cap_guard_ablation import build_fx_soft_cap_guard_ablation, guard_ablation_passes


def test_guard_ablation_relaxes_equity_trend() -> None:
    case = {
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

    assert guard_ablation_passes(case, "combined_dd_guard") is False
    assert guard_ablation_passes(case, "relaxed_equity_trend_guard") is True


def test_guard_ablation_builds_comparison() -> None:
    replay = {
        "cases": [
            {
                "classification": "overblocked_by_current",
                "current_final_action": "watch",
                "fx_flags": ["japan_fx_risk_caution"],
                "feature_snapshot": {
                    "acwi_spy_relative_13w": 0.01,
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

    payload = build_fx_soft_cap_guard_ablation(replay)

    assert payload["status"] == "ok"
    assert payload["candidates"]
