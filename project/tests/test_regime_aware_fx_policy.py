from __future__ import annotations

from project.regime_aware_fx_policy import evaluate_regime_aware_fx_policy


def test_regime_aware_fx_policy_blocks_rate_shock() -> None:
    case = {
        "current_final_action": "watch",
        "fx_flags": ["japan_fx_risk_caution"],
        "feature_snapshot": {
            "tnx_change_4w": 0.12,
            "acwi_return_13w": -0.02,
            "vix_level": 27.0,
            "hyg_lqd_ratio_return_4w": -0.02,
        },
    }

    result = evaluate_regime_aware_fx_policy(case, "normal_recovery_soft_cap")

    assert result["detected_regime"] == "rate_shock"
    assert result["applies"] is False
    assert result["affects_final_action"] is False


def test_regime_aware_fx_policy_allows_recovery_with_guard() -> None:
    case = {
        "current_final_action": "watch",
        "fx_flags": ["japan_fx_risk_caution"],
        "feature_snapshot": {
            "acwi_return_13w": 0.08,
            "acwi_return_4w": 0.03,
            "spy_return_13w": 0.05,
            "acwi_drawdown_13w": 0.0,
            "vix_level": 16.0,
            "vix_change_4w": -0.05,
            "hyg_lqd_ratio_return_4w": 0.01,
            "acwi_spy_relative_13w": 0.01,
        },
    }

    result = evaluate_regime_aware_fx_policy(case, "regime_aware_with_dd_guard")

    assert result["detected_regime"] == "recovery"
    assert result["applies"] is True
    assert result["candidate_action"] == "buy_candidate"
