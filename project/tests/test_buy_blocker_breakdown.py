from __future__ import annotations

from project.buy_blocker_breakdown import build_buy_blocker_breakdown


def test_buy_blocker_breakdown_classifies_fx_risk() -> None:
    payload = build_buy_blocker_breakdown(
        {
            "spot_signal": {
                "blocker_assessment": {"level": "caution", "flags": ["japan_fx_risk_moderate", "foreign_asset_fx_headwind"]},
                "action_layers": {"market_raw_action": "buy_window", "risk_adjusted_action": "watch", "final_action": "watch"},
                "recovery_evidence": {"grade": "confirmed"},
            },
            "japan_risk": {"flags": ["foreign_asset_fx_headwind"]},
            "risk_lines": {"stage_key": "normal"},
            "data_reliability": {"level": "high", "decision_allowed": True},
            "score": {"total_score": 0.72},
        }
    )

    assert payload["primary_blocker"] == "fx_risk"
    assert payload["affected_action_layer"] == "risk_adjusted"
    assert payload["affects_final_action"] is False


def test_buy_blocker_breakdown_classifies_sample_cap() -> None:
    payload = build_buy_blocker_breakdown(
        {
            "spot_signal": {
                "action_decision": {"reliability_cap_applied": True, "cap_reason": ["sample_fallback_present"]},
                "action_layers": {"market_raw_action": "buy_window", "risk_adjusted_action": "buy_window", "final_action": "watch"},
            },
            "data_reliability": {"level": "medium", "decision_allowed": True},
            "risk_lines": {"stage_key": "normal"},
            "score": {"total_score": 0.7},
        }
    )

    assert payload["primary_blocker"] == "sample_only"
    assert "sample_fallback_present" in payload["blocker_reasons"]["sample_only"]
