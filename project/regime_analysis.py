from __future__ import annotations

import pandas as pd

from project.indicators import adx_from_closes, max_drawdown, momentum, volatility_compression


def analyze_market_regime(
    prices: pd.DataFrame,
    returns: pd.DataFrame,
    credit_monitor: list[dict[str, object]] | None,
    inflation_monitor: list[dict[str, object]] | None,
    thresholds: dict[str, float],
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

    if regime_score >= thresholds["regime_risk_on_score"]:
        label = "risk_on"
    elif regime_score <= thresholds["regime_risk_off_score"]:
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

    return {
        "benchmark": benchmark,
        "regime_label": label,
        "regime_score": round(regime_score, 4),
        "trend_strength": round(trend_strength, 4),
        "momentum_12w": round(mom, 4),
        "max_drawdown": round(dd, 4),
        "volatility_compression": round(compression, 4),
        "credit_regime_flag": credit_context["flag"],
        "inflation_regime_flag": inflation_context["flag"],
    }


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
