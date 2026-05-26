from __future__ import annotations

from project.buy_decision_card import build_buy_decision_card


def test_buy_decision_card_summarizes_layers_and_unlock_conditions() -> None:
    card = build_buy_decision_card(
        {
            "spot_signal": {
                "action": "watch",
                "action_layers": {"market_raw_action": "buy_window", "risk_adjusted_action": "watch", "final_action": "watch"},
                "recovery_evidence": {"grade": "confirmed"},
                "blocker_assessment": {"level": "caution", "flags": ["foreign_asset_fx_headwind"]},
            },
            "japan_risk": {"flags": ["foreign_asset_fx_headwind"], "usd_jpy": {"change_4w": 0.03}},
            "risk_lines": {"stage_key": "normal"},
            "data_reliability": {"level": "high", "decision_allowed": True},
            "score": {"total_score": 0.7},
        }
    )

    assert card["final_action"] == "watch"
    assert card["market_raw_action"] == "buy_window"
    assert card["primary_blocker"] == "fx_risk"
    assert card["unlock_conditions"]
    assert card["affects_final_action"] is False
    assert "not a probability" in card["readiness_score_note"]


def test_buy_decision_card_marks_sample_only_context() -> None:
    card = build_buy_decision_card(
        {
            "spot_signal": {
                "action": "wait",
                "action_layers": {"market_raw_action": "wait", "risk_adjusted_action": "wait", "final_action": "wait"},
                "action_decision": {"reliability_cap_applied": True, "cap_reason": ["sample_fallback_present"]},
            },
            "data_reliability": {"level": "medium", "decision_allowed": True, "sample_fallback_count": 1},
            "risk_lines": {"stage_key": "normal"},
        }
    )

    assert card["final_action"] == "wait"
    assert card["primary_blocker"] == "sample_only"
    assert "sample fallback" in str(card["sample_only_note"])


def test_buy_decision_card_keeps_watch_action_when_caution_score_is_recalibrated() -> None:
    card = build_buy_decision_card(
        {
            "spot_signal": {
                "action": "watch",
                "action_layers": {"market_raw_action": "watch", "risk_adjusted_action": "watch", "final_action": "watch"},
                "recovery_evidence": {"grade": "building"},
                "blocker_assessment": {
                    "level": "caution",
                    "flags": ["rates_warning", "japan_fx_risk_moderate", "foreign_asset_fx_dependency"],
                },
            },
            "risk_lines": {"stage_key": "normal"},
            "data_reliability": {"level": "high", "decision_allowed": True},
            "score": {"total_score": 0.5789},
            "config": {"thresholds": {"spot_score_buy": 0.65}},
        }
    )

    assert card["final_action"] == "watch"
    assert card["market_raw_action"] == "watch"
    assert card["risk_adjusted_action"] == "watch"
    assert card["buy_readiness_score"] == 31
    assert card["affects_final_action"] is False
