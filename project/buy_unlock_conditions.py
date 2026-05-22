from __future__ import annotations

from typing import Any


def build_buy_unlock_conditions(blocker_breakdown: dict[str, Any], report: dict[str, Any] | None = None) -> dict[str, Any]:
    report = report or {}
    primary = blocker_breakdown.get("primary_blocker") or "unknown"
    conditions = _conditions_for(primary, report)
    return {
        "unlock_conditions": conditions,
        "condition_priority": [row["condition"] for row in conditions],
        "primary_blocker": primary,
        "affects_final_action": False,
        "policy_status": "explanatory_only",
    }


def _conditions_for(primary: str, report: dict[str, Any]) -> list[dict[str, Any]]:
    if primary == "fx_risk":
        return [
            _condition("foreign_asset_fx_headwind resolves", "foreign_asset_fx_headwind", "absent", "FX headwind is the main buy blocker."),
            _condition(
                "USDJPY 4w change stabilizes", _usdjpy_change(report), "within caution band", "Separate asset strength from yen move."
            ),
            _condition(
                "risk_stage remains normal/caution",
                _risk_stage(report),
                "normal or caution",
                "Do not soften FX while broader risk is stressed.",
            ),
        ]
    if primary == "risk_line":
        return [
            _condition(
                "risk_stage improves",
                _risk_stage(report),
                "normal or caution",
                "Danger-line conditions should clear before stronger buy labels.",
            ),
            _condition(
                "VIX / credit / rates triggers clear", _risk_reasons(report), "no active danger trigger", "Risk-line blocker is active."
            ),
        ]
    if primary == "credit_stress":
        return [_condition("credit proxy improves", "credit_stress", "neutral or improving", "Credit stress blocks buy candidates.")]
    if primary == "rate_shock":
        return [_condition("rates shock fades", "rate_shock", "not active", "Rate-shock regimes were weak in long-range replay.")]
    if primary == "data_quality":
        return [
            _condition(
                "data reliability improves",
                _reliability(report),
                "medium/high with decision_allowed",
                "Final action is capped by data quality.",
            )
        ]
    if primary == "sample_only":
        return [
            _condition(
                "live data replaces sample fallback",
                _reliability(report),
                "no sample fallback cap",
                "Sample-only output must not become a buy signal.",
            )
        ]
    if primary == "recovery_evidence_weak":
        return [
            _condition(
                "recovery evidence reaches building",
                _recovery_grade(report),
                "building or confirmed",
                "Recovery evidence is not strong enough.",
            )
        ]
    if primary == "score_shortfall":
        return [
            _condition(
                "market score approaches candidate/buy threshold",
                _score(report),
                "near candidate threshold",
                "Market score is below buy threshold.",
            )
        ]
    if primary == "drawdown_guard":
        return [_condition("drawdown context improves", "drawdown_guard", "guard not triggered", "DD guard remains diagnostic-only.")]
    return [
        _condition("confirm market score, risk stage, FX, and data quality", "-", "all clear", "No single classified blocker dominates.")
    ]


def _condition(condition: str, current: Any, target: str, reason: str) -> dict[str, Any]:
    return {
        "condition": condition,
        "current_value": current,
        "target_state": target,
        "reason": reason,
        "caveat": "This is an explanatory condition, not an automatic buy instruction.",
    }


def _risk_stage(report: dict[str, Any]) -> str:
    return str((report.get("risk_lines") or {}).get("stage_key", "-"))


def _risk_reasons(report: dict[str, Any]) -> list[str]:
    return [str(reason) for reason in (report.get("risk_lines") or {}).get("reasons", [])[:3]]


def _reliability(report: dict[str, Any]) -> str:
    reliability = report.get("data_reliability") or {}
    return f"{reliability.get('level', '-')}, decision_allowed={reliability.get('decision_allowed', '-')}"


def _recovery_grade(report: dict[str, Any]) -> str:
    return str(((report.get("spot_signal") or {}).get("recovery_evidence") or {}).get("grade", "-"))


def _score(report: dict[str, Any]) -> Any:
    return (report.get("score") or {}).get("total_score", ((report.get("spot_signal") or {}).get("score", "-")))


def _usdjpy_change(report: dict[str, Any]) -> Any:
    return ((report.get("japan_risk") or {}).get("usd_jpy") or {}).get("change_4w", "-")
