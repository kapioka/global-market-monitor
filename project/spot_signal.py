from __future__ import annotations

from typing import Any, Mapping

from project.reliability_policy import apply_reliability_policy
from project.signal_messages import (
    cycle_phase_rationale,
    japan_risk_penalty_summary,
    market_regime_rationale,
    penalty_summary,
    recovery_evidence_summary,
    reliability_cap_summary,
    risk_lines_summary,
    sector_adjustment_summary,
    summarize_credit_monitor,
    summarize_inflation_monitor,
    total_score_rationale,
)

DEFAULT_SPOT_WEIGHT = 0.02


def evaluate_spot_signal(
    score: dict[str, float],
    regime: dict[str, Any],
    cycle: dict[str, Any],
    credit_monitor: list[dict[str, Any]],
    inflation_monitor: list[dict[str, Any]],
    thresholds: dict[str, float],
    risk_lines: dict[str, Any] | None = None,
    sector_rotation: Mapping[str, Any] | None = None,
    sector_config: Mapping[str, float] | None = None,
    recovery_evidence: Mapping[str, Any] | None = None,
    japan_risk: Mapping[str, Any] | None = None,
    japan_risk_config: Mapping[str, float] | None = None,
    reliability_policy: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    total = score["total_score"]
    risk_off_relief_applied = _risk_off_relief_applied(regime, total, thresholds)
    regime_penalty = _regime_penalty(regime, total, thresholds, risk_lines)
    sector_adjustment, sector_adjustment_explain = _sector_spot_adjustment(sector_rotation, sector_config, regime.get("regime_label"))
    japan_risk_penalty = _japan_risk_penalty(japan_risk, japan_risk_config)
    adjusted_score = min(max(total - regime_penalty - japan_risk_penalty + sector_adjustment, 0.0), 1.0)
    legacy_action = _action_for_state(adjusted_score, regime, thresholds, risk_lines)
    second_leg_risk = _second_leg_risk(regime, cycle, risk_lines)
    credit_summary = summarize_credit_monitor(credit_monitor)
    inflation_summary = summarize_inflation_monitor(inflation_monitor)

    evidence = dict(recovery_evidence or _fallback_recovery_evidence(score, regime, cycle, credit_monitor, sector_rotation))
    blocker = _build_blocker_assessment(regime, risk_lines, sector_rotation, japan_risk)
    action_decision = _build_action_decision(evidence, blocker)
    action_decision = _apply_reliability_cap(action_decision, reliability_policy)

    rationale = [
        market_regime_rationale(regime["regime_label"]),
        cycle_phase_rationale(cycle["phase_label"]),
        total_score_rationale(total),
        penalty_summary(regime["regime_label"], regime_penalty, adjusted_score),
        credit_summary,
        inflation_summary,
    ]
    if abs(sector_adjustment) > 0:
        rationale.append(sector_adjustment_summary(sector_rotation, sector_adjustment))
    if japan_risk_penalty > 0:
        rationale.append(japan_risk_penalty_summary(japan_risk_penalty, japan_risk))
    if risk_lines:
        rationale.append(risk_lines_summary(risk_lines))
        rationale.extend(str(reason) for reason in risk_lines.get("reasons", [])[:3])
    if action_decision.get("reliability_cap_applied"):
        rationale.append(reliability_cap_summary(action_decision.get("action")))
    return {
        "action": action_decision["action"],
        "legacy_action": legacy_action,
        "score": total,
        "adjusted_score": round(adjusted_score, 4),
        "legacy_adjusted_score": round(adjusted_score, 4),
        "regime_penalty": round(regime_penalty, 4),
        "japan_risk_penalty": round(japan_risk_penalty, 4),
        "sector_adjustment": round(sector_adjustment, 4),
        "sector_adjustment_explain": sector_adjustment_explain,
        "risk_off_relief_applied": risk_off_relief_applied,
        "credit_stress_score": score.get("credit_stress_component"),
        "credit_summary": credit_summary,
        "second_leg_risk": second_leg_risk,
        "recovery_evidence": evidence,
        "blocker_assessment": blocker,
        "action_decision": action_decision,
        "rationale": rationale,
    }


def _fallback_recovery_evidence(
    score: Mapping[str, Any],
    regime: Mapping[str, Any],
    cycle: Mapping[str, Any],
    credit_monitor: list[dict[str, Any]],
    sector_rotation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    components = {
        "legacy_total_score": round(float(score.get("total_score", 0.5) or 0.5), 4),
        "credit_support": round(_credit_recovery_hint(credit_monitor), 4),
        "cycle_support": round(_cycle_support_hint(cycle), 4),
        "sector_support": round(_sector_support_hint(sector_rotation), 4),
    }
    raw_score = sum(components.values()) / len(components)
    if raw_score >= 0.68:
        grade = "confirmed"
    elif raw_score >= 0.52:
        grade = "building"
    else:
        grade = "weak"
    return {
        "score": round(raw_score, 4),
        "grade": grade,
        "components": components,
        "summary": recovery_evidence_summary(grade, regime, cycle),
    }


def _build_blocker_assessment(
    regime: Mapping[str, Any],
    risk_lines: Mapping[str, Any] | None,
    sector_rotation: Mapping[str, Any] | None,
    japan_risk: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if risk_lines:
        level = str(risk_lines.get("decision_level", "none"))
        flags = [str(flag) for flag in risk_lines.get("decision_flags", [])]
        summary = str(risk_lines.get("decision_summary", risk_lines.get("summary", "-")))
    else:
        level = "none"
        flags = []
        summary = "危険ライン判定がないため、強い blocker は確認されていません。"

    credit_flag = str(regime.get("credit_regime_flag", "neutral"))
    if credit_flag == "credit_stress_severe" and "credit_stress_severe" not in flags:
        flags.append("credit_stress_severe")
        level = "block"
        summary = "信用悪化が強く、追加投資判断はブロックすべき状態です。"
    elif credit_flag == "credit_stress_moderate" and level == "none":
        flags.append("credit_stress_moderate")
        level = "caution"
        summary = "信用悪化の火種が残るため、改善が見えても慎重に扱うべき状態です。"

    signals = dict((sector_rotation or {}).get("integration_signals", {}))
    if signals.get("single_sector_dominance_warning") and "single_sector_dominance_warning" not in flags:
        flags.append("single_sector_dominance_warning")
        if level == "none":
            level = "caution"
            summary = "一部セクター頼みの戻りになっており、騙し上昇を警戒したい状態です。"
    if signals.get("defensive_leadership") and "defensive_leadership" not in flags:
        flags.append("defensive_leadership")
        if level == "none":
            level = "caution"
            summary = "ディフェンシブ主導のため、上昇再開の質はまだ慎重に見たい状態です。"
    if signals.get("peakout_warning") and "peakout_warning" not in flags:
        flags.append("peakout_warning")
        if level == "none":
            level = "caution"
            summary = "内部構造に失速警戒があり、追加投資は監視を優先したい状態です。"

    japan_level = str((japan_risk or {}).get("level", "low"))
    japan_flags = [str(flag) for flag in (japan_risk or {}).get("flags", [])]
    if japan_level == "high" and "japan_fx_risk_high" not in flags:
        flags.append("japan_fx_risk_high")
        flags.extend(flag for flag in japan_flags if flag not in flags)
        if level == "none":
            level = "caution"
            summary = "円建て・為替リスクが高く、外貨建て資産の追加投資は監視を優先したい状態です。"
    elif japan_level == "moderate" and any(flag in {"fx_shock", "foreign_asset_fx_dependency", "foreign_asset_fx_headwind"} for flag in japan_flags):
        if "japan_fx_risk_moderate" not in flags:
            flags.append("japan_fx_risk_moderate")
        flags.extend(flag for flag in japan_flags if flag not in flags)
        if level == "none":
            level = "caution"
            summary = "円建て・為替リスクに注意が必要で、外貨建て資産は為替寄与を分けて確認したい状態です。"

    primary_reasons = flags[:3]
    return {
        "level": level,
        "flags": flags,
        "primary_reasons": primary_reasons,
        "summary": summary,
    }


def _japan_risk_penalty(japan_risk: Mapping[str, Any] | None, config: Mapping[str, float] | None) -> float:
    if not japan_risk:
        return 0.0
    level = str(japan_risk.get("level", "low"))
    flags = {str(flag) for flag in japan_risk.get("flags", [])}
    if not flags:
        return 0.0
    config = config or {}
    if level == "high":
        return float(config.get("spot_penalty_high", 0.04))
    if level == "moderate" and flags.intersection({"fx_shock", "foreign_asset_fx_dependency", "foreign_asset_fx_headwind"}):
        return float(config.get("spot_penalty_moderate", 0.02))
    return 0.0


def _build_action_decision(recovery_evidence: Mapping[str, Any], blocker_assessment: Mapping[str, Any]) -> dict[str, Any]:
    grade = str(recovery_evidence.get("grade", "weak"))
    evidence_score = float(recovery_evidence.get("score", 0.0) or 0.0)
    blocker_level = str(blocker_assessment.get("level", "none"))

    if blocker_level == "block":
        action = "wait"
        mode = "blocked_by_market_stress"
    elif grade == "confirmed" and blocker_level == "none":
        action = "buy_window"
        mode = "evidence_confirmed"
    elif grade in {"building", "confirmed"}:
        action = "watch"
        mode = "evidence_building_with_caution" if blocker_level == "caution" else "evidence_building"
    else:
        action = "wait"
        mode = "insufficient_recovery_evidence"

    return {
        "raw_action": action,
        "action": action,
        "raw_confidence": round(evidence_score, 4),
        "confidence": round(evidence_score, 4),
        "confidence_cap": 1.0,
        "reliability_cap_applied": False,
        "cap_reason": [],
        "max_action": "buy_window",
        "mode": mode,
        "reason_path": [grade, blocker_level],
    }


def _apply_reliability_cap(action_decision: dict[str, Any], reliability_policy: Mapping[str, Any] | None) -> dict[str, Any]:
    return apply_reliability_policy(action_decision, reliability_policy)


def _credit_recovery_hint(credit_monitor: list[dict[str, Any]]) -> float:
    if not credit_monitor:
        return 0.5
    by_ticker = {row["ticker"]: row for row in credit_monitor}
    ratio = by_ticker.get("HYG/LQD")
    if ratio and ratio.get("signal_label") == "信用改善":
        return 0.8
    if ratio and ratio.get("signal_label") == "信用収縮警戒":
        return 0.2
    return 0.5


def _cycle_support_hint(cycle: Mapping[str, Any]) -> float:
    mapping = {
        "recovery": 1.0,
        "upswing": 0.9,
        "late_cycle": 0.45,
        "downswing": 0.2,
        "insufficient_data": 0.5,
    }
    return float(mapping.get(str(cycle.get("phase_label", "")), 0.5))


def _sector_support_hint(sector_rotation: Mapping[str, Any] | None) -> float:
    signals = dict((sector_rotation or {}).get("integration_signals", {}))
    if not signals:
        return 0.5
    score = 0.5
    if signals.get("broad_improvement"):
        score += 0.2
    if signals.get("cyclical_improving"):
        score += 0.15
    if signals.get("defensive_leadership"):
        score -= 0.12
    if signals.get("peakout_warning"):
        score -= 0.15
    if signals.get("single_sector_dominance_warning"):
        score -= 0.08
    return min(max(score, 0.0), 1.0)


def _sector_spot_adjustment(
    sector_rotation: Mapping[str, Any] | None,
    sector_config: Mapping[str, float] | None,
    regime_label: str | None = None,
) -> tuple[float, list[dict[str, Any]]]:
    signals = dict((sector_rotation or {}).get("integration_signals", {}))
    if not signals:
        return 0.0, []
    weight = float((sector_config or {}).get("spot_signal_integration_weight", DEFAULT_SPOT_WEIGHT))
    adjustment = 0.0
    explain: list[dict[str, Any]] = []
    if signals.get("peakout_warning"):
        delta = -weight
        adjustment += delta
        explain.append({"signal": "peakout_warning", "delta": round(delta, 4)})
    if signals.get("defensive_leadership"):
        delta = -(weight * 0.5)
        adjustment += delta
        explain.append({"signal": "defensive_leadership", "delta": round(delta, 4)})
    if signals.get("broad_improvement"):
        delta = weight
        adjustment += delta
        explain.append({"signal": "broad_improvement", "delta": round(delta, 4)})
    if signals.get("cyclical_improving"):
        delta = weight * 0.5
        adjustment += delta
        explain.append({"signal": "cyclical_improving", "delta": round(delta, 4)})
    dominance_strength = _dominance_strength(signals)
    if signals.get("single_sector_dominance_warning"):
        delta = -(weight * _dominance_spot_penalty(regime_label) * _dominance_strength_multiplier(dominance_strength))
        adjustment += delta
        explain.append({"signal": "single_sector_dominance_warning", "delta": round(delta, 4), "regime": regime_label, "strength": dominance_strength})
    if signals.get("energy_dominance_warning"):
        delta = -(weight * 0.05)
        adjustment += delta
        explain.append({"signal": "energy_dominance_warning", "delta": round(delta, 4)})
    max_adjustment = float((sector_config or {}).get("max_sector_adjustment", 0.1))
    capped = max(min(adjustment, max_adjustment), -max_adjustment)
    if capped != adjustment:
        explain.append({"signal": "cap", "delta": round(capped - adjustment, 4)})
    return capped, explain



def _dominance_strength(signals: Mapping[str, Any]) -> str:
    normalized = str(signals.get("dominance_strength") or "").strip().lower()
    if normalized in {"weak", "medium", "strong"}:
        return normalized
    return "medium"


def _dominance_strength_multiplier(strength: str) -> float:
    if strength == "strong":
        return 1.3
    if strength == "weak":
        return 0.7
    return 1.0


def _dominance_spot_penalty(regime_label: str | None) -> float:
    normalized = str(regime_label or "").strip().lower()
    if normalized in {"risk_on", "early_recovery"}:
        return 0.2
    if normalized in {"risk_off", "credit_stress", "inflation_shock", "stagflation_warning"}:
        return 0.55
    return 0.45


def _action_for_state(adjusted_score: float, regime: dict[str, Any], thresholds: dict[str, float], risk_lines: dict[str, Any] | None) -> str:
    stage_key = str((risk_lines or {}).get("stage_key", "normal"))
    blocked_regimes = {"risk_off", "credit_stress", "stagflation_warning"}
    if stage_key == "extreme_danger_line_reached":
        return "wait"
    if adjusted_score >= thresholds["spot_score_buy"] and regime["regime_label"] not in blocked_regimes and stage_key not in {"credit_spillover_initial", "danger_line_reached"}:
        return "buy_window"
    if adjusted_score >= thresholds["spot_score_watch"]:
        return "watch"
    return "wait"


def _second_leg_risk(regime: dict[str, Any], cycle: dict[str, Any], risk_lines: dict[str, Any] | None) -> str:
    stage_key = str((risk_lines or {}).get("stage_key", "normal"))
    credit_flag = str(regime.get("credit_regime_flag", ""))
    if stage_key == "extreme_danger_line_reached":
        return "extreme"
    if stage_key == "danger_line_reached":
        return "high"
    if credit_flag == "credit_stress_severe":
        return "high"
    if regime["max_drawdown"] <= -0.12 and cycle["phase_label"] == "downswing":
        return "high"
    if stage_key in {"credit_spillover_initial", "caution"} or credit_flag == "credit_stress_moderate":
        return "moderate"
    return "low"


def _regime_penalty(regime: dict[str, Any], total_score: float, thresholds: dict[str, float], risk_lines: dict[str, Any] | None) -> float:
    regime_label = str(regime.get("regime_label", ""))
    credit_flag = str(regime.get("credit_regime_flag", ""))
    inflation_flag = str(regime.get("inflation_regime_flag", ""))
    if _risk_off_relief_applied(regime, total_score, thresholds):
        base = float(thresholds.get("penalty_risk_off_relief", 0.02))
    elif credit_flag == "credit_stress_severe":
        base = float(thresholds.get("penalty_credit_stress_severe", thresholds.get("penalty_credit_stress", 0.18)))
    elif credit_flag == "credit_stress_moderate":
        base = float(thresholds.get("penalty_credit_stress_moderate", thresholds.get("penalty_credit_stress", 0.18)))
    elif inflation_flag == "inflation_shock_broad":
        base = float(thresholds.get("penalty_inflation_shock_broad", thresholds.get("penalty_inflation_shock", 0.12)))
    elif inflation_flag == "inflation_shock_oil_only":
        base = float(thresholds.get("penalty_inflation_shock_oil_only", thresholds.get("penalty_inflation_shock", 0.12)))
    else:
        penalties = {
            "credit_stress": thresholds.get("penalty_credit_stress", 0.18),
            "inflation_shock": thresholds.get("penalty_inflation_shock", 0.12),
            "stagflation_warning": thresholds.get("penalty_stagflation_warning", 0.2),
            "risk_off": thresholds.get("penalty_risk_off", 0.08),
            "early_recovery": 0.0,
            "transition": thresholds.get("penalty_transition", 0.03),
            "risk_on": 0.0,
        }
        base = float(penalties.get(regime_label, 0.0))
    stress_penalty = float((risk_lines or {}).get("penalty_hint", 0.0) or 0.0)
    return min(base + stress_penalty, 0.35)


def _risk_off_relief_applied(regime: dict[str, Any], total_score: float, thresholds: dict[str, float]) -> bool:
    regime_label = str(regime.get("regime_label", ""))
    return regime_label == "risk_off" and total_score >= thresholds.get("penalty_risk_off_relief_score_min", 0.47)



