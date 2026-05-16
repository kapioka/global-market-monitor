from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from project.action_schema import action_rank, runtime_cap_action
from project.data_fetcher import FetchResult

LIVE_STATUSES = {"ok", "proxy_fallback"}
PROXY_STATUS = "proxy_fallback"
SAMPLE_STATUS = "sample_fallback"
UNAVAILABLE_STATUS = "unavailable"


def assess_data_reliability(config: Mapping[str, Any], fetch: FetchResult) -> dict[str, Any]:
    summary = dict(fetch.diagnostics.get("summary", {}))
    total = int(summary.get("requested_count", len(fetch.acquisition_log)) or len(fetch.acquisition_log) or 0)
    live_ok = sum(1 for item in fetch.acquisition_log if item.get("status") in LIVE_STATUSES)
    sample_count = int(
        summary.get(
            "sample_fallback_count",
            sum(1 for item in fetch.acquisition_log if item.get("status") == SAMPLE_STATUS),
        )
    )
    unavailable_count = int(
        summary.get(
            "unavailable_count",
            sum(1 for item in fetch.acquisition_log if item.get("status") == UNAVAILABLE_STATUS),
        )
    )
    proxy_count = int(
        summary.get(
            "proxy_fallback_count",
            sum(1 for item in fetch.acquisition_log if item.get("status") == PROXY_STATUS),
        )
    )
    live_ratio = round((live_ok / total), 4) if total else 0.0
    critical_set = critical_tickers(config)
    critical_failures = [
        str(item.get("requested_ticker", "-"))
        for item in fetch.acquisition_log
        if item.get("requested_ticker") in critical_set and item.get("status") in {SAMPLE_STATUS, UNAVAILABLE_STATUS}
    ]

    result = _base_result(
        live_ratio=live_ratio,
        sample_count=sample_count,
        unavailable_count=unavailable_count,
        proxy_count=proxy_count,
        critical_failures=critical_failures,
    )

    if fetch.source == "sample" or (total > 0 and live_ok == 0 and sample_count == total):
        return _finalize(
            result,
            level="diagnostic",
            decision_allowed=False,
            max_action="diagnostic_only",
            confidence_cap=0.0,
            watermark_required=True,
            reason_code="sample_only",
            reason="サンプルデータのみのため、投資判断ではなく診断用の出力です。",
            blocking=True,
        )

    if live_ratio < 0.6:
        return _finalize(
            result,
            level="low",
            decision_allowed=False,
            max_action="wait",
            confidence_cap=0.25,
            watermark_required=True,
            reason_code="live_ratio_below_60",
            reason=f"live 取得率が不足しているため、厳密な判断はできません。取得率: {live_ratio:.0%}",
            blocking=True,
        )

    if critical_failures:
        return _finalize(
            result,
            level="low",
            decision_allowed=True,
            max_action="watch",
            confidence_cap=0.45,
            watermark_required=True,
            reason_code="critical_series_unavailable",
            reason=f"重要系列 {', '.join(critical_failures)} が不足しているため、buy_window は抑制します。利用可能データでの暫定判定です。",
            blocking=False,
        )

    if sample_count > 0:
        return _finalize(
            result,
            level="medium",
            decision_allowed=True,
            max_action="watch",
            confidence_cap=0.45,
            watermark_required=True,
            reason_code="sample_fallback_present",
            reason="一部系列にサンプル代替が含まれるため、buy_window は抑制します。利用可能データで判定しています。",
            blocking=False,
        )

    if unavailable_count > 0:
        return _finalize(
            result,
            level="medium",
            decision_allowed=True,
            max_action="watch",
            confidence_cap=0.55,
            watermark_required=True,
            reason_code="unavailable_series_present",
            reason="一部系列が取得不能のため、buy_window は抑制します。利用可能データで判定しています。",
            blocking=False,
        )

    if live_ratio < 0.8:
        return _finalize(
            result,
            level="medium",
            decision_allowed=True,
            max_action="watch",
            confidence_cap=0.45,
            watermark_required=True,
            reason_code="live_ratio_below_80",
            reason=f"live 取得率がやや不足しているため、buy_window は抑制します。取得率: {live_ratio:.0%}",
            blocking=False,
        )

    if proxy_count > 0:
        return _finalize(
            result,
            level="medium",
            decision_allowed=True,
            max_action="buy_window",
            confidence_cap=0.75,
            watermark_required=False,
            reason_code="proxy_fallback_present",
            reason="一部系列に proxy 取得が含まれるため、confidence を抑制します。",
            blocking=False,
        )

    return _finalize(
        result,
        level="high",
        decision_allowed=True,
        max_action="buy_window",
        confidence_cap=1.0,
        watermark_required=False,
        reason_code="live_data_sufficient",
        reason="主要系列の live 取得は概ね維持できているため、厳密判定に近い状態です。",
        blocking=False,
    )


def apply_reliability_policy(action_decision: Mapping[str, Any], reliability: Mapping[str, Any] | None) -> dict[str, Any]:
    """Apply the final data-quality cap to an action decision.

    This is the single policy boundary that turns the market-only action into the
    final reportable action. Keep compatibility keys for existing reports while
    also exposing explicit original/final fields for downstream consumers.
    """
    original_action = str(
        action_decision.get("original_action") or action_decision.get("raw_action") or action_decision.get("action") or "wait"
    )
    original_confidence = float(
        action_decision.get("original_confidence") or action_decision.get("raw_confidence") or action_decision.get("confidence") or 0.0
    )
    active_policy = dict(reliability or {})
    max_action = str(active_policy.get("max_action", "buy_window"))
    cap_action = runtime_cap_action(max_action)
    confidence_cap = float(active_policy.get("confidence_cap", 1.0) or 0.0)
    reasons = _policy_reasons(active_policy)

    action_capped = action_rank(original_action) > action_rank(cap_action)
    confidence_capped = original_confidence > confidence_cap
    final_action = cap_action if action_capped else original_action
    final_confidence = min(original_confidence, confidence_cap)
    policy_triggered = bool(action_capped or confidence_capped)

    result = dict(action_decision)
    result.update(
        {
            "original_action": original_action,
            "final_action": final_action,
            "raw_action": original_action,
            "action": final_action,
            "original_confidence": round(original_confidence, 4),
            "final_confidence": round(final_confidence, 4),
            "raw_confidence": round(original_confidence, 4),
            "confidence": round(final_confidence, 4),
            "cap_level": max_action,
            "max_action": max_action,
            "confidence_cap": round(confidence_cap, 4),
            "policy_triggered": policy_triggered,
            "reliability_cap_applied": policy_triggered,
            "reasons": reasons,
            "policy_reasons": reasons,
            "cap_reason": reasons,
            "critical_failures": list(active_policy.get("critical_failures", [])),
            "live_ratio": active_policy.get("live_ratio", 1.0),
            "sample_fallback_count": int(active_policy.get("sample_fallback_count", 0) or 0),
            "proxy_fallback_count": int(active_policy.get("proxy_fallback_count", 0) or 0),
            "unavailable_count": int(active_policy.get("unavailable_count", 0) or 0),
        }
    )
    if action_capped:
        result["mode"] = f"{result.get('mode', 'decision')}_capped_by_reliability"
    if policy_triggered:
        result["reason_path"] = list(result.get("reason_path", [])) + reasons
    return result


def critical_tickers(config: Mapping[str, Any]) -> set[str]:
    critical = {"ACWI", "SPY", "^VIX", "HYG", "LQD", "USDJPY=X"}
    tickers = config.get("tickers", {})
    if isinstance(tickers, Mapping):
        global_equities = list(dict(tickers.get("global_equities", {})).values())
        if global_equities:
            critical.add(str(global_equities[0]))
        for section in ("credit",):
            values = tickers.get(section, {})
            if isinstance(values, Mapping):
                critical.update(str(value) for value in values.values())
        japan = tickers.get("japan", {})
        if isinstance(japan, Mapping):
            critical.update(str(value) for value in japan.values())
    return critical


def _policy_reasons(reliability: Mapping[str, Any]) -> list[str]:
    reasons = list(reliability.get("blocking_reasons", [])) + list(reliability.get("degrade_reasons", []))
    if not reasons and reliability.get("reason_code"):
        reasons = [str(reliability["reason_code"])]
    return [str(reason) for reason in reasons]


def _base_result(
    *,
    live_ratio: float,
    sample_count: int,
    unavailable_count: int,
    proxy_count: int,
    critical_failures: list[str],
) -> dict[str, Any]:
    return {
        "live_ratio": live_ratio,
        "sample_fallback_count": sample_count,
        "unavailable_count": unavailable_count,
        "proxy_fallback_count": proxy_count,
        "critical_failures": critical_failures,
        "blocking_reasons": [],
        "degrade_reasons": [],
    }


def _finalize(
    result: dict[str, Any],
    *,
    level: str,
    decision_allowed: bool,
    max_action: str,
    confidence_cap: float,
    watermark_required: bool,
    reason_code: str,
    reason: str,
    blocking: bool,
) -> dict[str, Any]:
    target = "blocking_reasons" if blocking else "degrade_reasons"
    result[target].append(reason_code)
    result.update(
        {
            "level": level,
            "decision_allowed": decision_allowed,
            "max_action": max_action,
            "confidence_cap": confidence_cap,
            "watermark_required": watermark_required,
            "reason_code": reason_code,
            "reason": reason,
            "summary": reason,
        }
    )
    return result
