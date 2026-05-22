from __future__ import annotations

from project.fx_conditional_soft_cap import evaluate_all_conditional_candidates, evaluate_conditional_fx_soft_cap


def test_combined_conservative_accepts_clean_fx_only_case() -> None:
    case = {
        "risk_stage": "normal",
        "reliability_level": "historical_price_replay",
        "market_raw_action": "buy_candidate",
        "current_final_action": "watch",
        "score_band": "strong",
        "fx_flags": ["japan_fx_risk_caution"],
        "feature_snapshot": {
            "hyg_lqd_ratio_return_4w": 0.01,
            "vix_level": 18.0,
            "vix_change_4w": 0.02,
            "usdjpy_change_4w": -0.03,
            "tnx_change_4w": 0.02,
        },
    }

    result = evaluate_conditional_fx_soft_cap(case, "combined_conservative")

    assert result["applies"] is True
    assert result["action"] == "buy_candidate"
    assert result["affects_final_action"] is False


def test_combined_conservative_rejects_credit_and_vix_shock() -> None:
    case = {
        "risk_stage": "normal",
        "reliability_level": "high",
        "market_raw_action": "buy_candidate",
        "current_final_action": "watch",
        "score_band": "strong",
        "fx_flags": ["japan_fx_risk_caution"],
        "feature_snapshot": {"hyg_lqd_ratio_return_4w": -0.05, "vix_level": 35.0},
    }

    result = evaluate_conditional_fx_soft_cap(case, "combined_conservative")

    assert result["applies"] is False
    assert "no_credit_stress" in result["failed_conditions"]
    assert "no_vix_shock" in result["failed_conditions"]
    assert set(evaluate_all_conditional_candidates(case)) == {
        "normal_high_reliability",
        "normal_or_caution_no_credit_stress",
        "score_gap_limited",
        "combined_conservative",
    }
