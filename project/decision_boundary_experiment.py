from __future__ import annotations

from typing import Any

LEVEL_PENALTIES = {
    "normal": 0,
    "watch": -4,
    "caution": -8,
    "block": -12,
    "unavailable": 0,
}


def build_decision_boundary_experiment(report: dict[str, Any]) -> dict[str, Any]:
    card = report.get("buy_decision_card") or {}
    integrated = report.get("japan_resident_integrated_risk_context") or {}
    baseline_action = str(card.get("final_action") or "-")
    baseline_score = _int_score(card.get("buy_readiness_score"))
    supplemental_level = _normalize_level(integrated.get("combined_context_level"))
    raw_score_delta = LEVEL_PENALTIES.get(supplemental_level, 0)
    raw_adjusted_score = baseline_score + raw_score_delta
    adjusted_score = _clamp_score(raw_adjusted_score)
    clamped_score_delta = adjusted_score - baseline_score
    suggested_adjustment = _suggested_adjustment(supplemental_level, raw_score_delta)
    return {
        "title": "Decision Boundary Experiment",
        "enabled": False,
        "status": "experimental_display_only",
        "baseline": {
            "final_action": baseline_action,
            "buy_readiness_score": baseline_score,
        },
        "experimental": {
            "final_action": baseline_action,
            "adjusted_buy_readiness_score": adjusted_score,
            "supplemental_warning_level": supplemental_level,
            "suggested_adjustment": suggested_adjustment,
            "raw_score_delta": raw_score_delta,
            "clamped_score_delta": clamped_score_delta,
            "clamp_reason": _clamp_reason(baseline_score, raw_adjusted_score),
        },
        "diff": {
            "score_delta": clamped_score_delta,
            "raw_score_delta": raw_score_delta,
            "clamped_score_delta": clamped_score_delta,
            "clamp_reason": _clamp_reason(baseline_score, raw_adjusted_score),
            "action_changed": False,
            "baseline_final_action_preserved": True,
        },
        "inputs": {
            "uses_japan_resident_integrated_risk_context": bool(integrated),
            "combined_context_level": supplemental_level,
            "source_sections": integrated.get("source_sections", []),
        },
        "must_not_affect_production_default": True,
        "must_not_change_threshold_json": True,
        "must_not_change_reliability_policy": True,
        "caveat": "This experiment compares a supplemental boundary only. It does not change production final_action or buy_readiness_score.",
    }


def _int_score(value: Any) -> int:
    try:
        return _clamp_score(int(value))
    except (TypeError, ValueError):
        return 0


def _clamp_score(value: int) -> int:
    return max(0, min(100, value))


def _normalize_level(level: Any) -> str:
    value = str(level or "unavailable").lower()
    if value in {"block", "high", "danger", "extreme"}:
        return "block"
    if value in {"caution", "medium", "moderate", "review"}:
        return "caution"
    if value in {"watch", "low", "weak"}:
        return "watch"
    if value in {"normal", "ok", "stable", "none"}:
        return "normal"
    return "unavailable"


def _suggested_adjustment(level: str, score_delta: int) -> str:
    if score_delta == 0:
        return "no_experimental_score_adjustment"
    if level == "block":
        return "experimental_hard_warning_score_discount"
    if level == "caution":
        return "experimental_caution_score_discount"
    if level == "watch":
        return "experimental_watch_score_discount"
    return "no_experimental_score_adjustment"


def _clamp_reason(baseline_score: int, raw_adjusted_score: int) -> str:
    if raw_adjusted_score < 0:
        return "baseline already at floor" if baseline_score == 0 else "adjusted score clamped at floor"
    if raw_adjusted_score > 100:
        return "adjusted score clamped at ceiling"
    return "not_clamped"
