from __future__ import annotations

from typing import Any

from project.fx_soft_cap_dd_guard import evaluate_dd_guard
from project.market_regime_classifier import classify_market_regime

REGIME_AWARE_CANDIDATES = (
    "recovery_only_soft_cap",
    "normal_recovery_soft_cap",
    "stress_block_soft_cap",
    "conservative_regime_aware",
    "regime_aware_with_dd_guard",
)

STRESS_REGIMES = {"rate_shock", "risk_off", "credit_stress", "crash_or_drawdown", "inflation_shock"}


def evaluate_regime_aware_fx_policy(case: dict[str, Any], candidate: str) -> dict[str, Any]:
    if candidate not in REGIME_AWARE_CANDIDATES:
        raise ValueError(f"unknown regime-aware FX policy candidate: {candidate}")
    regime_info = classify_market_regime(case)
    regime = str(regime_info.get("regime", "uncertain"))
    fx_flags = set(case.get("fx_flags") or [])
    decision = _candidate_decision(case, candidate, regime, fx_flags)
    return {
        "candidate_name": candidate,
        "candidate_action": "buy_candidate" if decision["applies"] else str(case.get("current_final_action", "watch")),
        "applies": decision["applies"],
        "applies_to_regime": regime,
        "detected_regime": regime,
        "regime_reasons": regime_info.get("regime_reasons", []),
        "regime_confidence": regime_info.get("regime_confidence", "low"),
        "stress_families": regime_info.get("stress_families", []),
        "block_reason": decision.get("block_reason"),
        "soft_cap_reason": decision.get("soft_cap_reason"),
        "affects_final_action": False,
        "policy_status": "diagnostic_only",
    }


def evaluate_all_regime_aware_fx_policies(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {candidate: evaluate_regime_aware_fx_policy(case, candidate) for candidate in REGIME_AWARE_CANDIDATES}


def _candidate_decision(case: dict[str, Any], candidate: str, regime: str, fx_flags: set[str]) -> dict[str, Any]:
    if candidate == "recovery_only_soft_cap":
        if regime == "recovery":
            return _soft("recovery_regime_allows_fx_soft_cap")
        return _block(f"{regime}_not_recovery")
    if candidate == "normal_recovery_soft_cap":
        if regime in {"normal", "recovery"}:
            return _soft(f"{regime}_allows_fx_soft_cap")
        if regime == "fx_stress" and "foreign_asset_fx_headwind" not in fx_flags:
            return _soft("mild_fx_stress_allows_soft_cap")
        return _block(f"{regime}_blocks_soft_cap")
    if candidate == "stress_block_soft_cap":
        if regime in STRESS_REGIMES:
            return _block(f"{regime}_stress_block")
        if regime in {"normal", "recovery", "fx_stress"}:
            return _soft(f"{regime}_soft_cap")
        return _block("uncertain_regime_current_policy")
    if candidate == "conservative_regime_aware":
        if regime == "recovery" and case.get("risk_stage") == "normal" and case.get("reliability_level") in {"high", "historical_price_replay"}:
            return _soft("recovery_high_reliability_normal_risk")
        return _block("conservative_conditions_not_met")
    if candidate == "regime_aware_with_dd_guard":
        if regime not in {"normal", "recovery", "fx_stress"}:
            return _block(f"{regime}_not_allowed")
        guard = evaluate_dd_guard(case, "combined_dd_guard")
        if guard["passes"]:
            return _soft("regime_allowed_and_dd_guard_passed")
        return _block("dd_guard_block:" + ",".join(guard.get("blocked_reasons", [])[:3]))
    return _block("unknown_candidate")


def _soft(reason: str) -> dict[str, Any]:
    return {"applies": True, "soft_cap_reason": reason, "block_reason": None}


def _block(reason: str) -> dict[str, Any]:
    return {"applies": False, "soft_cap_reason": None, "block_reason": reason}
