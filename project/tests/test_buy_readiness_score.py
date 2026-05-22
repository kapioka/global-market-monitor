from __future__ import annotations

from project.buy_blocker_breakdown import build_buy_blocker_breakdown
from project.buy_readiness_score import build_buy_readiness_score


def test_buy_readiness_score_is_bounded_and_explanatory() -> None:
    report = {
        "spot_signal": {
            "action_layers": {"market_raw_action": "buy_window", "risk_adjusted_action": "watch", "final_action": "watch"},
            "recovery_evidence": {"grade": "confirmed"},
            "blocker_assessment": {"flags": ["foreign_asset_fx_headwind"]},
        },
        "risk_lines": {"stage_key": "normal"},
        "data_reliability": {"level": "high", "decision_allowed": True},
        "japan_risk": {"flags": ["foreign_asset_fx_headwind"]},
        "score": {"total_score": 0.7},
    }
    blockers = build_buy_blocker_breakdown(report)
    payload = build_buy_readiness_score(report, blockers)

    assert 0 <= payload["buy_readiness_score"] <= 100
    assert payload["affects_final_action"] is False
    assert "FX risk is blocking buy clarity" in payload["negative_factors"]


def test_buy_readiness_score_penalizes_low_data_quality() -> None:
    payload = build_buy_readiness_score(
        {
            "spot_signal": {"action_layers": {"market_raw_action": "wait", "risk_adjusted_action": "wait", "final_action": "wait"}},
            "risk_lines": {"stage_key": "normal"},
            "data_reliability": {"level": "low", "decision_allowed": False},
            "score": {"total_score": 0.2},
        }
    )

    assert payload["readiness_level"] == "far"
