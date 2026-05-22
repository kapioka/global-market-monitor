from __future__ import annotations

from typing import Any

CANDIDATE_NAMES = ("normal_high_reliability", "normal_or_caution_no_credit_stress", "score_gap_limited", "combined_conservative")
FX_FLAG_TOKENS = ("fx", "japan_fx", "foreign_asset")


def evaluate_conditional_fx_soft_cap(case: dict[str, Any], candidate: str) -> dict[str, Any]:
    if candidate not in CANDIDATE_NAMES:
        raise ValueError(f"unknown conditional fx_soft_cap candidate: {candidate}")
    checks = _checks(case)
    if candidate == "normal_high_reliability":
        passed = checks["risk_normal"] and checks["reliability_high"] and checks["fx_only"] and checks["raw_candidate"] and checks["current_blocked"]
    elif candidate == "normal_or_caution_no_credit_stress":
        passed = (
            checks["risk_normal_or_caution"]
            and checks["reliability_medium_or_high"]
            and checks["no_credit_stress"]
            and checks["no_vix_shock"]
            and checks["no_usdjpy_shock"]
            and checks["raw_candidate"]
        )
    elif candidate == "score_gap_limited":
        passed = checks["score_gap_limited"] and checks["recovery_building"] and checks["fx_only"] and checks["raw_candidate"]
    else:
        passed = (
            checks["risk_normal"]
            and checks["reliability_high"]
            and checks["fx_only"]
            and checks["recovery_building"]
            and checks["score_gap_limited"]
            and checks["no_vix_shock"]
            and checks["no_credit_stress"]
            and checks["no_rates_shock"]
            and checks["no_usdjpy_shock"]
        )
    return {
        "candidate": candidate,
        "applies": passed,
        "action": "buy_candidate" if passed else str(case.get("current_final_action", "watch")),
        "failed_conditions": [name for name, value in checks.items() if not value],
        "affects_final_action": False,
        "policy_status": "diagnostic_only",
    }


def evaluate_all_conditional_candidates(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {candidate: evaluate_conditional_fx_soft_cap(case, candidate) for candidate in CANDIDATE_NAMES}


def _checks(case: dict[str, Any]) -> dict[str, bool]:
    features = case.get("feature_snapshot") or {}
    flags = [str(flag) for flag in case.get("fx_flags", []) or []]
    blocker_flags = [str(flag) for flag in case.get("blocker_flags", []) or []]
    risk_stage = str(case.get("risk_stage") or "normal")
    reliability = str(case.get("reliability_level") or "")
    score_band = str(case.get("score_band") or "")
    raw_action = str(case.get("market_raw_action") or case.get("raw_action") or "buy_candidate")
    current = str(case.get("current_final_action") or "watch")
    recovery_grade = str((case.get("recovery_evidence") or {}).get("grade") or "building")
    credit_4w = _num(features.get("hyg_lqd_ratio_return_4w"))
    vix_level = _num(features.get("vix_level"))
    vix_change_4w = _num(features.get("vix_change_4w"))
    usdjpy_4w = _num(features.get("usdjpy_change_4w"))
    tnx_4w = _num(features.get("tnx_change_4w"))
    return {
        "risk_normal": risk_stage == "normal",
        "risk_normal_or_caution": risk_stage in {"normal", "caution"},
        "reliability_high": reliability in {"high", "historical_price_replay"},
        "reliability_medium_or_high": reliability in {"medium", "high", "historical_price_replay"},
        "fx_only": bool(flags) and all(_is_fx_flag(flag) for flag in flags + blocker_flags),
        "raw_candidate": raw_action in {"buy_window", "buy_candidate"},
        "current_blocked": current in {"watch", "wait"},
        "score_gap_limited": score_band in {"candidate", "strong"} or _score_value(case) >= 0.55,
        "recovery_building": recovery_grade in {"building", "confirmed", "strong", "historical_price_replay"},
        "no_credit_stress": credit_4w is None or credit_4w >= -0.02,
        "no_vix_shock": (vix_level is None or vix_level < 30.0) and (vix_change_4w is None or vix_change_4w < 0.25),
        "no_usdjpy_shock": usdjpy_4w is None or abs(usdjpy_4w) < 0.06,
        "no_rates_shock": tnx_4w is None or abs(tnx_4w) < 0.15,
    }


def _is_fx_flag(flag: str) -> bool:
    lowered = flag.lower()
    return any(token in lowered for token in FX_FLAG_TOKENS)


def _score_value(case: dict[str, Any]) -> float:
    try:
        return float(case.get("score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
