from __future__ import annotations

from typing import Any


def score_market(
    regime: dict[str, Any],
    cycle: dict[str, Any],
    credit_monitor: list[dict[str, Any]],
    weights: dict[str, float],
    thresholds: dict[str, float],
) -> dict[str, float]:
    trend_component = 1.0 if regime["trend_strength"] >= thresholds["adx_trend_strong"] else 0.45
    momentum_component = min(max((regime["momentum_12w"] + 0.1) / 0.2, 0.0), 1.0)
    breadth_proxy_component = 0.7 if regime["regime_label"] == "risk_on" else 0.35
    drawdown_component = min(max((regime["max_drawdown"] + 0.25) / 0.25, 0.0), 1.0)
    volatility_component = (
        1.0 if regime["volatility_compression"] <= thresholds["volatility_compression_ratio"] else 0.4
    )
    macro_proxy_component = 0.7 if cycle["phase_label"] in {"recovery", "upswing"} else 0.3
    credit_stress_component = _credit_stress_component(credit_monitor)

    total = (
        trend_component * weights["trend"]
        + momentum_component * weights["momentum"]
        + breadth_proxy_component * weights["breadth_proxy"]
        + drawdown_component * weights["drawdown"]
        + volatility_component * weights["volatility"]
        + macro_proxy_component * weights["macro_proxy"]
        + credit_stress_component * weights.get("credit_stress", 0.0)
    )

    return {
        "trend_component": round(trend_component, 4),
        "momentum_component": round(momentum_component, 4),
        "breadth_proxy_component": round(breadth_proxy_component, 4),
        "drawdown_component": round(drawdown_component, 4),
        "volatility_component": round(volatility_component, 4),
        "macro_proxy_component": round(macro_proxy_component, 4),
        "credit_stress_component": round(credit_stress_component, 4),
        "total_score": round(total, 4),
    }


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
