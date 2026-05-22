from __future__ import annotations

from typing import Any

GUARD_NAMES = ("equity_trend_guard", "volatility_guard", "credit_guard", "drawdown_context_guard", "combined_dd_guard")


def evaluate_dd_guard(case: dict[str, Any], guard: str) -> dict[str, Any]:
    if guard not in GUARD_NAMES:
        raise ValueError(f"unknown DD guard: {guard}")
    checks = _checks(case)
    if guard == "equity_trend_guard":
        passed = checks["equity_trend_ok"]
    elif guard == "volatility_guard":
        passed = checks["volatility_ok"]
    elif guard == "credit_guard":
        passed = checks["credit_ok"]
    elif guard == "drawdown_context_guard":
        passed = checks["drawdown_context_ok"]
    else:
        passed = (
            checks["equity_trend_ok"]
            and checks["volatility_ok"]
            and checks["credit_ok"]
            and checks["drawdown_context_ok"]
            and checks["recovery_context_ok"]
            and checks["fx_headwind_ok"]
        )
    return {
        "guard": guard,
        "passes": passed,
        "action": "buy_candidate" if passed else str(case.get("current_final_action", "watch")),
        "blocked_reasons": [name for name, value in checks.items() if not value],
        "affects_final_action": False,
        "policy_status": "diagnostic_only",
    }


def evaluate_all_dd_guards(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {guard: evaluate_dd_guard(case, guard) for guard in GUARD_NAMES}


def _checks(case: dict[str, Any]) -> dict[str, bool]:
    features = case.get("feature_snapshot") or {}
    fx_flags = set(case.get("fx_flags", []) or [])
    equity_trend = _num(features.get("acwi_spy_relative_13w"))
    vix_level = _num(features.get("vix_level"))
    vix_change = _num(features.get("vix_change_4w"))
    credit = _num(features.get("hyg_lqd_ratio_return_4w"))
    current_drawdown = _num(features.get("acwi_drawdown_13w"))
    acwi_4w = _num(features.get("acwi_return_4w"))
    acwi_13w = _num(features.get("acwi_return_13w"))
    oil = _num(features.get("oil_family_return_4w"))
    return {
        "equity_trend_ok": equity_trend is None or equity_trend >= -0.01,
        "volatility_ok": (vix_level is None or vix_level < 25.0) and (vix_change is None or vix_change < 0.15),
        "credit_ok": credit is None or credit >= -0.01,
        "drawdown_context_ok": (current_drawdown is None or current_drawdown > -0.03) and (acwi_4w is None or acwi_4w >= 0.0),
        "recovery_context_ok": acwi_13w is None or acwi_13w >= 0.04,
        "fx_headwind_ok": "foreign_asset_fx_headwind" not in fx_flags or (equity_trend is not None and equity_trend >= 0.0),
        "oil_shock_ok": oil is None or oil < 0.12,
    }


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
