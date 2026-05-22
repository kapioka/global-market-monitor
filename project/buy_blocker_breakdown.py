from __future__ import annotations

from typing import Any


BLOCKER_ORDER = [
    "sample_only",
    "data_quality",
    "reliability_policy_cap",
    "risk_line",
    "credit_stress",
    "rate_shock",
    "inflation_shock",
    "fx_risk",
    "drawdown_guard",
    "regime_mismatch",
    "recovery_evidence_weak",
    "score_shortfall",
    "unknown",
]

SEVERITY_SCORE = {"block": 100, "high": 85, "caution": 65, "medium": 50, "low": 25, "info": 10}


def build_buy_blocker_breakdown(report: dict[str, Any]) -> dict[str, Any]:
    spot_signal = report.get("spot_signal") or {}
    action_layers = spot_signal.get("action_layers") or {}
    action_decision = spot_signal.get("action_decision") or {}
    reliability = report.get("data_reliability") or report.get("reliability_policy") or {}
    risk_lines = report.get("risk_lines") or {}
    blocker_assessment = spot_signal.get("blocker_assessment") or {}
    recovery = spot_signal.get("recovery_evidence") or {}
    score = report.get("score") or {}
    flags = _all_flags(report)

    blockers: dict[str, dict[str, Any]] = {}
    _add_data_quality(blockers, reliability, action_decision)
    _add_risk_line(blockers, risk_lines)
    _add_flag_blockers(blockers, flags)
    _add_recovery_blocker(blockers, recovery)
    _add_score_blocker(blockers, score, report)

    if not blockers and str(blocker_assessment.get("level", "none")) not in {"none", "low"}:
        _add(blockers, "unknown", "caution", "blocker_assessment has caution but no classified reason", "risk_adjusted")

    ranked = sorted(
        blockers.values(),
        key=lambda row: (-int(row["severity_score"]), BLOCKER_ORDER.index(row["blocker"]) if row["blocker"] in BLOCKER_ORDER else 999),
    )
    primary = ranked[0]["blocker"] if ranked else None
    return {
        "blockers": ranked,
        "blocker_rank": [row["blocker"] for row in ranked],
        "primary_blocker": primary,
        "secondary_blockers": [row["blocker"] for row in ranked[1:]],
        "blocker_reasons": {row["blocker"]: row["reasons"] for row in ranked},
        "blocker_severity": {row["blocker"]: row["severity"] for row in ranked},
        "affected_action_layer": _affected_action_layer(action_layers, action_decision),
        "affects_final_action": False,
        "policy_status": "explanatory_only",
    }


def _add_data_quality(blockers: dict[str, dict[str, Any]], reliability: dict[str, Any], action_decision: dict[str, Any]) -> None:
    if str(reliability.get("level", "")).lower() == "low" or not reliability.get("decision_allowed", True):
        _add(blockers, "data_quality", "block", str(reliability.get("reason") or "data quality blocks decision"), "final")
    if action_decision.get("reliability_cap_applied"):
        reasons = action_decision.get("policy_reasons") or action_decision.get("cap_reason") or reliability.get("degrade_reasons") or []
        for reason in reasons or ["reliability policy cap applied"]:
            normalized = str(reason)
            category = "sample_only" if "sample" in normalized else "reliability_policy_cap"
            _add(blockers, category, "caution", normalized, "final")


def _add_risk_line(blockers: dict[str, dict[str, Any]], risk_lines: dict[str, Any]) -> None:
    stage = str(risk_lines.get("stage_key", "normal"))
    if stage in {"danger_line_reached", "extreme_danger_line_reached", "credit_spillover_initial"}:
        severity = "block" if stage == "extreme_danger_line_reached" else "high"
        _add(blockers, "risk_line", severity, stage, "risk_adjusted")
    for reason in risk_lines.get("reasons", [])[:3]:
        reason_text = str(reason).lower()
        if "金利" in reason_text or "rate" in reason_text or "tnx" in reason_text:
            _add(blockers, "rate_shock", "high", str(reason), "risk_adjusted")
        if "信用" in reason_text or "credit" in reason_text or "hyg" in reason_text:
            _add(blockers, "credit_stress", "high", str(reason), "risk_adjusted")


def _add_flag_blockers(blockers: dict[str, dict[str, Any]], flags: list[str]) -> None:
    for flag in flags:
        lower = flag.lower()
        if any(token in lower for token in ("japan_fx", "fx_", "foreign_asset_fx", "yen")):
            _add(blockers, "fx_risk", "caution", flag, "risk_adjusted")
        elif "credit" in lower:
            _add(blockers, "credit_stress", "high", flag, "risk_adjusted")
        elif "inflation" in lower or "oil" in lower:
            _add(blockers, "inflation_shock", "high", flag, "risk_adjusted")
        elif "rate" in lower or "tnx" in lower:
            _add(blockers, "rate_shock", "high", flag, "risk_adjusted")
        elif "drawdown" in lower or "dd_guard" in lower:
            _add(blockers, "drawdown_guard", "high", flag, "risk_adjusted")
        elif "regime" in lower or "risk_off" in lower:
            _add(blockers, "regime_mismatch", "caution", flag, "risk_adjusted")


def _add_recovery_blocker(blockers: dict[str, dict[str, Any]], recovery: dict[str, Any]) -> None:
    grade = str(recovery.get("grade", "weak"))
    if grade in {"weak", "guarded"}:
        _add(blockers, "recovery_evidence_weak", "medium", f"recovery_evidence:{grade}", "market_raw")


def _add_score_blocker(blockers: dict[str, dict[str, Any]], score: dict[str, Any], report: dict[str, Any]) -> None:
    thresholds = (report.get("config") or {}).get("thresholds") or {}
    buy_threshold = float(thresholds.get("spot_score_buy", 0.65))
    total = score.get("total_score")
    if total is None:
        return
    try:
        score_value = float(total)
    except (TypeError, ValueError):
        return
    if score_value < buy_threshold:
        _add(blockers, "score_shortfall", "medium", f"score {score_value:.2f} below buy threshold {buy_threshold:.2f}", "market_raw")


def _all_flags(report: dict[str, Any]) -> list[str]:
    spot_signal = report.get("spot_signal") or {}
    blocker = spot_signal.get("blocker_assessment") or {}
    japan_risk = report.get("japan_risk") or {}
    flags: list[str] = []
    for source in (blocker.get("flags", []), blocker.get("primary_reasons", []), japan_risk.get("flags", [])):
        flags.extend(str(flag) for flag in source)
    return list(dict.fromkeys(flags))


def _add(blockers: dict[str, dict[str, Any]], blocker: str, severity: str, reason: str, layer: str) -> None:
    row = blockers.setdefault(
        blocker,
        {
            "blocker": blocker,
            "severity": severity,
            "severity_score": SEVERITY_SCORE.get(severity, 0),
            "reasons": [],
            "affected_action_layer": layer,
        },
    )
    if SEVERITY_SCORE.get(severity, 0) > int(row["severity_score"]):
        row["severity"] = severity
        row["severity_score"] = SEVERITY_SCORE.get(severity, 0)
    if reason not in row["reasons"]:
        row["reasons"].append(reason)


def _affected_action_layer(action_layers: dict[str, Any], action_decision: dict[str, Any]) -> str:
    raw = str(
        action_layers.get("market_raw_action") or action_decision.get("market_raw_action") or action_decision.get("raw_action") or "wait"
    )
    risk = str(
        action_layers.get("risk_adjusted_action")
        or action_decision.get("risk_adjusted_action")
        or action_decision.get("raw_action")
        or "wait"
    )
    final = str(action_layers.get("final_action") or action_decision.get("final_action") or action_decision.get("action") or "wait")
    if raw != risk:
        return "risk_adjusted"
    if risk != final:
        return "final"
    return "market_raw"
