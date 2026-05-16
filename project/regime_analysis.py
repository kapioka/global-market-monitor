from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from project.indicators import adx_from_closes, max_drawdown, momentum, volatility_compression


DEFAULT_SECTOR_REGIME_WEIGHT = 0.03


def analyze_market_regime(
    prices: pd.DataFrame,
    returns: pd.DataFrame,
    credit_monitor: list[dict[str, object]] | None,
    inflation_monitor: list[dict[str, object]] | None,
    thresholds: dict[str, float],
    sector_rotation: Mapping[str, Any] | None = None,
    sector_config: Mapping[str, float] | None = None,
) -> dict[str, object]:
    benchmark = "ACWI" if "ACWI" in prices.columns else prices.columns[0]
    series = prices[benchmark]
    ret = returns[benchmark]

    trend_strength = adx_from_closes(series)
    mom = momentum(series, window=12)
    dd = max_drawdown(series)
    compression = volatility_compression(ret)

    regime_score = 0.0
    regime_score += 0.3 if mom > 0 else -0.3
    regime_score += 0.2 if trend_strength >= thresholds["adx_trend_strong"] else -0.05
    regime_score += 0.25 if dd > thresholds["drawdown_alert"] else -0.25
    regime_score += 0.15 if compression < thresholds["volatility_compression_ratio"] else -0.1

    provisional_adjustment, _ = _sector_regime_adjustment(sector_rotation, sector_config, inferred_regime=None)
    adjusted_regime_score = regime_score + provisional_adjustment
    if adjusted_regime_score >= thresholds["regime_risk_on_score"]:
        label = "risk_on"
    elif adjusted_regime_score <= thresholds["regime_risk_off_score"]:
        label = "risk_off"
    else:
        label = "transition"

    credit_context = _credit_context(credit_monitor or [])
    inflation_context = _inflation_context(inflation_monitor or [])
    if credit_context["is_credit_stress"]:
        label = "credit_stress"
    elif inflation_context["is_stagflation_warning"]:
        label = "stagflation_warning"
    elif inflation_context["is_inflation_shock"]:
        label = "inflation_shock"
    elif _is_early_recovery(
        base_label=label,
        credit_context=credit_context,
        momentum_12w=mom,
        trend_strength=trend_strength,
        thresholds=thresholds,
    ):
        label = "early_recovery"

    sector_adjustment, sector_adjustment_explain = _sector_regime_adjustment(sector_rotation, sector_config, inferred_regime=label)
    adjusted_regime_score = regime_score + sector_adjustment

    return {
        "benchmark": benchmark,
        "regime_label": label,
        "regime_score": round(regime_score, 4),
        "sector_vector_adjustment": round(sector_adjustment, 4),
        "adjusted_regime_score": round(adjusted_regime_score, 4),
        "sector_internal_structure": str((sector_rotation or {}).get("internal_structure", {}).get("structure_label", "Noisy / Unclear")),
        "sector_adjustment_explain": sector_adjustment_explain,
        "trend_strength": round(trend_strength, 4),
        "momentum_12w": round(mom, 4),
        "max_drawdown": round(dd, 4),
        "volatility_compression": round(compression, 4),
        "credit_regime_flag": credit_context["flag"],
        "inflation_regime_flag": inflation_context["flag"],
    }


def _sector_regime_adjustment(
    sector_rotation: Mapping[str, Any] | None,
    sector_config: Mapping[str, float] | None,
    inferred_regime: str | None = None,
) -> tuple[float, list[dict[str, Any]]]:
    signals = dict((sector_rotation or {}).get("integration_signals", {}))
    if not signals:
        return 0.0, []
    weight = float((sector_config or {}).get("regime_bonus_weight", DEFAULT_SECTOR_REGIME_WEIGHT))
    adjustment = 0.0
    explain: list[dict[str, Any]] = []
    if signals.get("defensive_leadership"):
        delta = -weight
        adjustment += delta
        explain.append({"signal": "defensive_leadership", "delta": round(delta, 4)})
    if signals.get("peakout_warning"):
        delta = -(weight * 0.6)
        adjustment += delta
        explain.append({"signal": "peakout_warning", "delta": round(delta, 4)})
    if signals.get("cyclical_improving"):
        delta = weight
        adjustment += delta
        explain.append({"signal": "cyclical_improving", "delta": round(delta, 4)})
    if signals.get("broad_improvement"):
        delta = weight * 0.5
        adjustment += delta
        explain.append({"signal": "broad_improvement", "delta": round(delta, 4)})
    dominance_penalty = _dominance_penalty_multiplier(inferred_regime)
    dominance_strength = _dominance_strength(signals)
    if signals.get("single_sector_dominance_warning"):
        delta = -(weight * dominance_penalty * _dominance_strength_multiplier(dominance_strength))
        adjustment += delta
        explain.append({"signal": "single_sector_dominance_warning", "delta": round(delta, 4), "regime": inferred_regime, "strength": dominance_strength})
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


def _dominance_penalty_multiplier(regime_label: str | None) -> float:
    normalized = str(regime_label or "").strip().lower()
    if normalized in {"risk_on", "early_recovery"}:
        return 0.18
    if normalized in {"risk_off", "credit_stress", "inflation_shock", "stagflation_warning"}:
        return 0.45
    return 0.35


def _credit_context(credit_monitor: list[dict[str, object]]) -> dict[str, object]:
    by_ticker = {str(row.get("ticker")): row for row in credit_monitor}
    ratio = by_ticker.get("HYG/LQD", {})
    hyg = by_ticker.get("HYG", {})

    ratio_signal = ratio.get("signal_label")
    hyg_signal = hyg.get("signal_label")
    ratio_change_4w = float(ratio.get("change_4w", 0.0) or 0.0)

    severe = ratio_signal == "信用収縮警戒" and hyg_signal == "弱含み"
    moderate = ratio_signal == "信用収縮警戒" or (hyg_signal == "弱含み" and ratio_change_4w <= -0.01)
    if severe:
        return {"is_credit_stress": True, "is_credit_improving": False, "flag": "credit_stress_severe"}
    if moderate:
        return {"is_credit_stress": True, "is_credit_improving": False, "flag": "credit_stress_moderate"}
    if ratio_signal == "信用改善" and ratio_change_4w >= 0:
        return {"is_credit_stress": False, "is_credit_improving": True, "flag": "credit_improving"}
    return {"is_credit_stress": False, "is_credit_improving": False, "flag": "neutral"}


def _is_early_recovery(
    base_label: str,
    credit_context: dict[str, object],
    momentum_12w: float,
    trend_strength: float,
    thresholds: dict[str, float],
) -> bool:
    if base_label not in {"transition", "risk_off"}:
        return False
    if not credit_context["is_credit_improving"]:
        return False
    if momentum_12w <= 0:
        return False
    return trend_strength >= thresholds["adx_trend_strong"] * 0.7


def _inflation_context(inflation_monitor: list[dict[str, object]]) -> dict[str, object]:
    by_ticker = {str(row.get("ticker")): row for row in inflation_monitor}
    oil = by_ticker.get("CL=F", {})
    gold = by_ticker.get("GC=F", {})
    dollar = by_ticker.get("DX-Y.NYB", {})

    oil_signal = oil.get("signal_label")
    gold_signal = gold.get("signal_label")
    dollar_signal = dollar.get("signal_label")
    oil_change_4w = float(oil.get("change_4w", 0.0) or 0.0)

    is_inflation_shock_broad = oil_signal == "インフレ圧力上昇" and dollar_signal == "ドル高進行"
    is_inflation_shock_oil_only = oil_signal == "インフレ圧力上昇" and not is_inflation_shock_broad
    is_stagflation_warning = is_inflation_shock_broad and gold_signal == "安全資産選好"
    if is_stagflation_warning:
        return {"is_inflation_shock": True, "is_stagflation_warning": True, "flag": "stagflation_warning"}
    if is_inflation_shock_broad:
        return {"is_inflation_shock": True, "is_stagflation_warning": False, "flag": "inflation_shock_broad"}
    if is_inflation_shock_oil_only or (oil_signal == "インフレ圧力上昇" and oil_change_4w >= 0.08):
        return {"is_inflation_shock": True, "is_stagflation_warning": False, "flag": "inflation_shock_oil_only"}
    return {"is_inflation_shock": False, "is_stagflation_warning": False, "flag": "neutral"}
