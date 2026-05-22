from __future__ import annotations

from typing import Any

from project.buy_blocker_breakdown import build_buy_blocker_breakdown
from project.buy_readiness_score import build_buy_readiness_score
from project.buy_unlock_conditions import build_buy_unlock_conditions


def build_buy_decision_card(report: dict[str, Any]) -> dict[str, Any]:
    spot_signal = report.get("spot_signal") or {}
    action_layers = spot_signal.get("action_layers") or {}
    action_decision = spot_signal.get("action_decision") or {}
    blockers = build_buy_blocker_breakdown(report)
    readiness = build_buy_readiness_score(report, blockers)
    unlock = build_buy_unlock_conditions(blockers, report)
    final_action = str(
        action_layers.get("final_action")
        or action_decision.get("final_action")
        or action_decision.get("action")
        or spot_signal.get("action")
        or "wait"
    )
    market_raw = str(
        action_layers.get("market_raw_action")
        or action_decision.get("market_raw_action")
        or action_decision.get("raw_action")
        or final_action
    )
    risk_adjusted = str(
        action_layers.get("risk_adjusted_action")
        or action_decision.get("risk_adjusted_action")
        or action_decision.get("raw_action")
        or final_action
    )
    return {
        "final_action": final_action,
        "market_raw_action": market_raw,
        "risk_adjusted_action": risk_adjusted,
        "buy_readiness_score": readiness["buy_readiness_score"],
        "readiness_level": readiness["readiness_level"],
        "positive_factors": readiness["positive_factors"],
        "negative_factors": readiness["negative_factors"],
        "primary_blocker": blockers.get("primary_blocker"),
        "secondary_blockers": blockers.get("secondary_blockers", []),
        "blocker_breakdown": blockers,
        "unlock_conditions": unlock.get("unlock_conditions", []),
        "policy_status": "explanatory_only",
        "affects_final_action": False,
        "caveat": "This card explains buy-decision clarity and does not change final_action.",
    }
