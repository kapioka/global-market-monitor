from __future__ import annotations

from typing import Any, Mapping


def score_recovery_evidence(
    regime: dict[str, Any],
    cycle: dict[str, Any],
    credit_monitor: list[dict[str, Any]],
    thresholds: dict[str, float],
    sector_rotation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    trend_component = 1.0 if regime["trend_strength"] >= thresholds["adx_trend_strong"] else 0.45
    momentum_component = min(max((regime["momentum_12w"] + 0.1) / 0.2, 0.0), 1.0)
    drawdown_component = min(max((regime["max_drawdown"] + 0.25) / 0.25, 0.0), 1.0)
    volatility_component = 1.0 if regime["volatility_compression"] <= thresholds["volatility_compression_ratio"] else 0.4
    credit_component = _credit_repair_component(credit_monitor)
    cycle_component = _cycle_support_component(cycle)
    sector_component, sector_explain = _sector_recovery_component(sector_rotation)

    components = {
        "trend_confirmation": round(trend_component, 4),
        "momentum_confirmation": round(momentum_component, 4),
        "drawdown_recovery_context": round(drawdown_component, 4),
        "volatility_repair": round(volatility_component, 4),
        "credit_repair": round(credit_component, 4),
        "cycle_support": round(cycle_component, 4),
        "sector_support": round(sector_component, 4),
    }
    score = sum(components.values()) / len(components)
    if score >= 0.68:
        grade = "confirmed"
    elif score >= 0.52:
        grade = "building"
    else:
        grade = "weak"
    return {
        "score": round(score, 4),
        "grade": grade,
        "components": components,
        "sector_explain": sector_explain,
        "summary": _recovery_summary(grade, regime, cycle),
    }


def score_market(
    regime: dict[str, Any],
    cycle: dict[str, Any],
    credit_monitor: list[dict[str, Any]],
    weights: dict[str, float],
    thresholds: dict[str, float],
    risk_monitor: list[dict[str, Any]] | None = None,
    sector_rotation: Mapping[str, Any] | None = None,
    sector_config: Mapping[str, float] | None = None,
) -> dict[str, float]:
    trend_component = 1.0 if regime["trend_strength"] >= thresholds["adx_trend_strong"] else 0.45
    momentum_component = min(max((regime["momentum_12w"] + 0.1) / 0.2, 0.0), 1.0)
    breadth_proxy_component = 0.7 if regime["regime_label"] == "risk_on" else 0.35
    drawdown_component = min(max((regime["max_drawdown"] + 0.25) / 0.25, 0.0), 1.0)
    volatility_component = 1.0 if regime["volatility_compression"] <= thresholds["volatility_compression_ratio"] else 0.4
    macro_proxy_component = 0.7 if cycle["phase_label"] in {"recovery", "upswing"} else 0.3
    credit_stress_component = _credit_stress_component(credit_monitor)
    stress_component = _stress_component(risk_monitor or [])
    sector_integration_component, sector_integration_explain = _sector_integration_component(sector_rotation, regime.get("regime_label"))

    components = {
        "trend_component": trend_component,
        "momentum_component": momentum_component,
        "breadth_proxy_component": breadth_proxy_component,
        "drawdown_component": drawdown_component,
        "volatility_component": volatility_component,
        "macro_proxy_component": macro_proxy_component,
        "credit_stress_component": credit_stress_component,
        "stress_component": stress_component,
        "sector_integration_component": sector_integration_component,
    }
    weight_map = {
        "trend_component": weights.get("trend", 0.0),
        "momentum_component": weights.get("momentum", 0.0),
        "breadth_proxy_component": weights.get("breadth_proxy", 0.0),
        "drawdown_component": weights.get("drawdown", 0.0),
        "volatility_component": weights.get("volatility", 0.0),
        "macro_proxy_component": weights.get("macro_proxy", 0.0),
        "credit_stress_component": weights.get("credit_stress", 0.0),
        "stress_component": weights.get("stress", 0.08),
        "sector_integration_component": float((sector_config or {}).get("ranking_integration_weight", 0.02)),
    }
    total_weight = sum(weight for weight in weight_map.values() if weight > 0)
    total = sum(components[key] * weight_map[key] for key in components) / total_weight if total_weight else sum(components.values()) / len(components)

    return {
        "trend_component": round(trend_component, 4),
        "momentum_component": round(momentum_component, 4),
        "breadth_proxy_component": round(breadth_proxy_component, 4),
        "drawdown_component": round(drawdown_component, 4),
        "volatility_component": round(volatility_component, 4),
        "macro_proxy_component": round(macro_proxy_component, 4),
        "credit_stress_component": round(credit_stress_component, 4),
        "stress_component": round(stress_component, 4),
        "sector_integration_component": round(sector_integration_component, 4),
        "sector_integration_explain": sector_integration_explain,
        "total_score": round(total, 4),
    }


def _sector_integration_component(sector_rotation: Mapping[str, Any] | None, regime_label: str | None = None) -> tuple[float, list[dict[str, Any]]]:
    signals = dict((sector_rotation or {}).get("integration_signals", {}))
    if not signals:
        return 0.5, []

    score = 0.5
    explain: list[dict[str, Any]] = []
    if signals.get("cyclical_improving"):
        score += 0.18
        explain.append({"signal": "cyclical_improving", "delta": 0.18})
    if signals.get("broad_improvement"):
        score += 0.14
        explain.append({"signal": "broad_improvement", "delta": 0.14})
    if signals.get("defensive_leadership"):
        score -= 0.14
        explain.append({"signal": "defensive_leadership", "delta": -0.14})
    if signals.get("peakout_warning"):
        score -= 0.2
        explain.append({"signal": "peakout_warning", "delta": -0.2})
    if signals.get("narrow_leadership"):
        score -= 0.1
        explain.append({"signal": "narrow_leadership", "delta": -0.1})
    dominance_strength = _dominance_strength(signals)
    if signals.get("single_sector_dominance_warning"):
        delta = -(_dominance_component_penalty(regime_label) * _dominance_strength_multiplier(dominance_strength))
        score += delta
        explain.append({"signal": "single_sector_dominance_warning", "delta": round(delta, 4), "regime": regime_label, "strength": dominance_strength})
    if signals.get("energy_dominance_warning"):
        score -= 0.01
        explain.append({"signal": "energy_dominance_warning", "delta": -0.01})
    bounded = min(max(score, 0.0), 1.0)
    return bounded, explain



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


def _dominance_component_penalty(regime_label: str | None) -> float:
    normalized = str(regime_label or "").strip().lower()
    if normalized in {"risk_on", "early_recovery"}:
        return 0.03
    if normalized in {"risk_off", "credit_stress", "inflation_shock", "stagflation_warning"}:
        return 0.1
    return 0.07


def _credit_stress_component(credit_monitor: list[dict[str, Any]]) -> float:
    if not credit_monitor:
        return 0.5
    by_ticker = {row["ticker"]: row for row in credit_monitor}
    ratio = by_ticker.get("HYG/LQD")
    hyg = by_ticker.get("HYG")
    lqd = by_ticker.get("LQD")

    signals: list[float] = []
    if ratio:
        signals.append(_bounded_score(ratio.get("zscore"), 0.0, 2.5))
        signals.append(_bounded_score(ratio.get("change_4w"), 0.0, 0.08))
    if hyg:
        signals.append(_bounded_score(hyg.get("change_4w"), 0.0, 0.08))
        signals.append(_bounded_score(hyg.get("zscore"), 0.0, 2.5))
    if lqd:
        signals.append(_bounded_score(lqd.get("change_4w"), 0.0, 0.05))
    if not signals:
        return 0.5
    return min(max(sum(signals) / len(signals), 0.0), 1.0)


def _credit_repair_component(credit_monitor: list[dict[str, Any]]) -> float:
    if not credit_monitor:
        return 0.5
    by_ticker = {row["ticker"]: row for row in credit_monitor}
    ratio = by_ticker.get("HYG/LQD")
    hyg = by_ticker.get("HYG")

    signals: list[float] = []
    if ratio:
        signals.append(_bounded_score(ratio.get("change_4w"), 0.0, 0.06))
        signals.append(_bounded_score(ratio.get("zscore"), 0.0, 2.0))
    if hyg:
        signals.append(_bounded_score(hyg.get("change_4w"), 0.0, 0.06))
        signals.append(_bounded_score(hyg.get("zscore"), 0.0, 2.0))
    if not signals:
        return 0.5
    return min(max(sum(signals) / len(signals), 0.0), 1.0)


def _stress_component(risk_monitor: list[dict[str, Any]]) -> float:
    if not risk_monitor:
        return 0.5
    weighted = 0.0
    total_weight = 0.0
    for row in risk_monitor:
        weight = float(row.get("weight", 1.0) or 1.0)
        health = float(row.get("health_score", 0.5) or 0.5)
        weighted += weight * health
        total_weight += weight
    if total_weight <= 0:
        return 0.5
    return min(max(weighted / total_weight, 0.0), 1.0)


def _cycle_support_component(cycle: dict[str, Any]) -> float:
    mapping = {
        "recovery": 1.0,
        "upswing": 0.9,
        "late_cycle": 0.45,
        "downswing": 0.2,
        "insufficient_data": 0.5,
    }
    return float(mapping.get(str(cycle.get("phase_label", "")), 0.5))


def _sector_recovery_component(sector_rotation: Mapping[str, Any] | None) -> tuple[float, list[dict[str, Any]]]:
    signals = dict((sector_rotation or {}).get("integration_signals", {}))
    if not signals:
        return 0.5, []
    score = 0.5
    explain: list[dict[str, Any]] = []
    if signals.get("broad_improvement"):
        score += 0.22
        explain.append({"signal": "broad_improvement", "delta": 0.22})
    if signals.get("cyclical_improving"):
        score += 0.18
        explain.append({"signal": "cyclical_improving", "delta": 0.18})
    if signals.get("defensive_leadership"):
        score -= 0.14
        explain.append({"signal": "defensive_leadership", "delta": -0.14})
    if signals.get("peakout_warning"):
        score -= 0.18
        explain.append({"signal": "peakout_warning", "delta": -0.18})
    if signals.get("single_sector_dominance_warning"):
        score -= 0.1
        explain.append({"signal": "single_sector_dominance_warning", "delta": -0.1})
    return min(max(score, 0.0), 1.0), explain


def _recovery_summary(grade: str, regime: dict[str, Any], cycle: dict[str, Any]) -> str:
    if grade == "confirmed":
        return f"回復確認は強めです。レジーム {regime.get('regime_label', '-')} とサイクル {cycle.get('phase_label', '-')} でも上昇再開の根拠が揃っています。"
    if grade == "building":
        return f"回復確認は改善途中です。レジーム {regime.get('regime_label', '-')} とサイクル {cycle.get('phase_label', '-')} は前向きですが、確証までは届いていません。"
    return f"回復確認はまだ弱めです。レジーム {regime.get('regime_label', '-')} とサイクル {cycle.get('phase_label', '-')} からも追加投資の根拠は限定的です。"


def _bounded_score(value: Any, center: float, scale: float) -> float:
    if value is None:
        return 0.5
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.5
    if scale == 0:
        return 0.5
    normalized = 0.5 + ((numeric - center) / scale) * 0.5
    return min(max(normalized, 0.0), 1.0)
