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
