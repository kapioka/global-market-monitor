from __future__ import annotations

from typing import Any

REGIME_NAMES = (
    "normal",
    "recovery",
    "risk_off",
    "rate_shock",
    "inflation_shock",
    "fx_stress",
    "credit_stress",
    "crash_or_drawdown",
    "uncertain",
)


def classify_market_regime(case_or_features: dict[str, Any]) -> dict[str, Any]:
    features = _feature_map(case_or_features)
    fx_flags = set(case_or_features.get("fx_flags") or [])
    stress: list[str] = []
    reasons: list[str] = []

    acwi_13w = _num(features.get("acwi_return_13w"))
    acwi_4w = _num(features.get("acwi_return_4w"))
    spy_13w = _num(features.get("spy_return_13w"))
    drawdown = _num(features.get("acwi_drawdown_13w"))
    vix = _num(features.get("vix_level"))
    vix_change = _num(features.get("vix_change_4w"))
    credit = _num(features.get("hyg_lqd_ratio_return_4w"))
    tnx = _num(features.get("tnx_change_4w"))
    usd_4w = _num(features.get("usdjpy_change_4w"))
    usd_13w = _num(features.get("usdjpy_change_13w"))
    oil = _num(features.get("oil_family_return_4w"))

    if tnx is not None and tnx >= 0.08 and (acwi_13w is None or acwi_13w < 0.04):
        stress.append("rates")
        reasons.append("rates_up_with_weak_equity")
    if vix is not None and vix >= 25.0:
        stress.append("volatility")
        reasons.append("vix_high")
    if vix_change is not None and vix_change >= 0.25:
        stress.append("volatility")
        reasons.append("vix_rising")
    if credit is not None and credit <= -0.015:
        stress.append("credit")
        reasons.append("credit_proxy_weak")
    if drawdown is not None and drawdown <= -0.10:
        stress.append("drawdown")
        reasons.append("deep_drawdown")
    if acwi_13w is not None and acwi_13w <= -0.06:
        stress.append("equity")
        reasons.append("equity_trend_weak")
    if oil is not None and oil >= 0.15:
        stress.append("inflation")
        reasons.append("oil_shock")
    if _fx_stress(usd_4w, usd_13w, fx_flags):
        stress.append("fx")
        reasons.append("fx_move_or_headwind")

    regime = _regime_from_signals(acwi_13w, acwi_4w, spy_13w, drawdown, vix, vix_change, credit, tnx, oil, stress, reasons)
    confidence = _confidence(regime, features, reasons)
    return {
        "regime": regime,
        "regime_reasons": reasons or ["insufficient_or_neutral_signals"],
        "regime_confidence": confidence,
        "stress_families": sorted(set(stress)),
        "risk_stage": case_or_features.get("risk_stage", "unknown"),
        "feature_snapshot": features,
    }


def _regime_from_signals(
    acwi_13w: float | None,
    acwi_4w: float | None,
    spy_13w: float | None,
    drawdown: float | None,
    vix: float | None,
    vix_change: float | None,
    credit: float | None,
    tnx: float | None,
    oil: float | None,
    stress: list[str],
    reasons: list[str],
) -> str:
    if "rates" in stress and ("credit" in stress or "volatility" in stress or "equity" in stress or "fx" in stress):
        return "rate_shock"
    if "inflation" in stress and ("rates" in stress or "equity" in stress):
        return "inflation_shock"
    if "credit" in stress and ("volatility" in stress or "equity" in stress):
        return "credit_stress"
    if "drawdown" in stress:
        return "crash_or_drawdown"
    if "volatility" in stress and ("equity" in stress or (drawdown is not None and drawdown <= -0.06)):
        return "risk_off"
    if _is_recovery(acwi_13w, acwi_4w, spy_13w, drawdown, vix, vix_change, credit):
        reasons.append("equity_and_credit_recovery")
        return "recovery"
    if "fx" in stress and len(set(stress)) == 1:
        return "fx_stress"
    if _has_enough_features(acwi_13w, acwi_4w, drawdown, vix, credit, tnx, oil):
        return "normal"
    return "uncertain"


def _is_recovery(
    acwi_13w: float | None,
    acwi_4w: float | None,
    spy_13w: float | None,
    drawdown: float | None,
    vix: float | None,
    vix_change: float | None,
    credit: float | None,
) -> bool:
    equity_recovering = (acwi_13w is not None and acwi_13w >= 0.04) and (acwi_4w is None or acwi_4w >= 0.0)
    spy_support = spy_13w is None or spy_13w >= 0.03
    drawdown_ok = drawdown is None or drawdown > -0.06
    vol_ok = (vix is None or vix < 24.0) and (vix_change is None or vix_change < 0.10)
    credit_ok = credit is None or credit >= -0.005
    return equity_recovering and spy_support and drawdown_ok and vol_ok and credit_ok


def _fx_stress(usd_4w: float | None, usd_13w: float | None, fx_flags: set[str]) -> bool:
    return (
        bool(fx_flags.intersection({"japan_fx_risk_caution", "japan_fx_risk_moderate", "foreign_asset_fx_headwind"}))
        or (usd_4w is not None and abs(usd_4w) >= 0.03)
        or (usd_13w is not None and abs(usd_13w) >= 0.06)
    )


def _has_enough_features(*values: float | None) -> bool:
    return sum(1 for value in values if value is not None) >= 4


def _confidence(regime: str, features: dict[str, Any], reasons: list[str]) -> str:
    if regime == "uncertain":
        return "low"
    available = sum(1 for value in features.values() if value is not None)
    if available >= 7 and reasons:
        return "high"
    if available >= 4:
        return "medium"
    return "low"


def _feature_map(case_or_features: dict[str, Any]) -> dict[str, Any]:
    features = dict(case_or_features.get("feature_snapshot") or {})
    for key, value in case_or_features.items():
        if key.endswith(("_4w", "_13w")) or key in {"vix_level", "hyg_lqd_ratio_return_4w", "tnx_change_4w", "oil_family_return_4w"}:
            features.setdefault(key, value)
    return features


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
