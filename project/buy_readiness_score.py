from __future__ import annotations

from typing import Any


ACTION_POINTS = {"wait": 0, "watch": 12, "buy_candidate": 25, "buy_window": 35}
STRESS_PENALTIES_BY_SEVERITY = {"info": 0, "low": 3, "medium": 6, "caution": 9, "high": 25, "block": 30}


def build_buy_readiness_score(report: dict[str, Any], blocker_breakdown: dict[str, Any] | None = None) -> dict[str, Any]:
    spot_signal = report.get("spot_signal") or {}
    action_layers = spot_signal.get("action_layers") or {}
    action_decision = spot_signal.get("action_decision") or {}
    risk_lines = report.get("risk_lines") or {}
    reliability = report.get("data_reliability") or report.get("reliability_policy") or {}
    recovery = spot_signal.get("recovery_evidence") or {}
    diagnostics = report.get("buy_window_diagnostics") or {}
    blocker_breakdown = blocker_breakdown or {}

    raw_action = str(
        action_layers.get("market_raw_action")
        or action_decision.get("market_raw_action")
        or action_decision.get("raw_action")
        or spot_signal.get("action")
        or "wait"
    )
    risk_action = str(
        action_layers.get("risk_adjusted_action")
        or action_decision.get("risk_adjusted_action")
        or action_decision.get("raw_action")
        or "wait"
    )

    score = 10
    positive: list[str] = []
    negative: list[str] = []
    reasons: list[str] = []
    readiness_cap: int | None = None

    raw_points = ACTION_POINTS.get(raw_action, 0)
    score += raw_points
    reasons.append(f"market_raw_action:{raw_action}+{raw_points}")
    if raw_action in {"buy_candidate", "buy_window"}:
        positive.append(f"market_raw_action is {raw_action}")

    if risk_action in {"buy_candidate", "buy_window"}:
        score += 20
        positive.append(f"risk_adjusted_action is {risk_action}")
    elif raw_action in {"buy_candidate", "buy_window"}:
        negative.append(f"risk_adjusted_action downgraded to {risk_action}")

    if str(risk_lines.get("stage_key", "normal")) == "normal":
        score += 10
        positive.append("risk_stage is normal")
    elif str(risk_lines.get("stage_key", "")).startswith("extreme"):
        score -= 25
        negative.append("risk_stage is extreme")

    if str(reliability.get("level", "")).lower() == "high":
        score += 10
        positive.append("data reliability is high")
    elif str(reliability.get("level", "")).lower() == "low":
        score -= 30
        negative.append("data reliability is low")

    grade = str(recovery.get("grade", "weak"))
    if grade in {"building", "confirmed"}:
        score += 10
        positive.append(f"recovery evidence is {grade}")
    else:
        score -= 10
        negative.append(f"recovery evidence is {grade}")

    perf = diagnostics.get("buy_candidate_performance") or {}
    if _positive_validation(perf):
        score += 10
        positive.append("historical validation is positive")

    for blocker in blocker_breakdown.get("blockers", []):
        category = blocker.get("blocker")
        if category == "fx_risk":
            score -= _stress_penalty(blocker)
            negative.append("FX risk is blocking buy clarity")
        elif category in {"credit_stress", "rate_shock", "risk_line"}:
            score -= _stress_penalty(blocker)
            negative.append(f"{category} is active")
        elif category in {"data_quality", "sample_only"}:
            score -= 30
            readiness_cap = 10
            negative.append(f"{category} caps action")
        elif category == "score_shortfall":
            score -= 3
            negative.append("score is below buy threshold")
        elif category == "recovery_evidence_weak":
            score -= 10

    final_score = max(0, min(100, int(round(score))))
    if readiness_cap is not None:
        final_score = min(final_score, readiness_cap)
    return {
        "buy_readiness_score": final_score,
        "readiness_level": readiness_level(final_score),
        "positive_factors": list(dict.fromkeys(positive)),
        "negative_factors": list(dict.fromkeys(negative)),
        "score_reasons": reasons,
        "affects_final_action": False,
        "policy_status": "explanatory_only",
    }


def readiness_level(score: int) -> str:
    if score >= 80:
        return "buy_window_zone"
    if score >= 60:
        return "candidate_zone"
    if score >= 45:
        return "near_candidate"
    if score >= 30:
        return "watch"
    return "far"


def _positive_validation(perf: dict[str, Any]) -> bool:
    for horizon in ("13w", "26w"):
        row = perf.get(horizon) or {}
        value = row.get("mean_excess_return") if isinstance(row, dict) else None
        if value is not None:
            try:
                return float(value) > 0
            except (TypeError, ValueError):
                return False
    return False


def _stress_penalty(blocker: dict[str, Any]) -> int:
    return STRESS_PENALTIES_BY_SEVERITY.get(str(blocker.get("severity", "high")), 25)
