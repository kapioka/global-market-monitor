from __future__ import annotations

from typing import Any


def build_threshold_certainty(
    *,
    active_summary: dict[str, Any] | None = None,
    proposed_summary: dict[str, Any] | None = None,
    candidate_summary: dict[str, Any] | None = None,
    metadata_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata_counts = (metadata_summary or {}).get("counts", {})
    return {
        "active": _certainty_for_set("active", active_summary or {}, metadata_counts, operational=True),
        "proposed": _certainty_for_set("proposed", proposed_summary or {}, metadata_counts, operational=False),
        "candidate_v2": _certainty_for_set("candidate_v2", candidate_summary or {}, metadata_counts, operational=False),
    }


def _certainty_for_set(label: str, summary: dict[str, Any], metadata_counts: dict[str, Any], operational: bool) -> dict[str, Any]:
    action_counts = summary.get("action_counts") or summary.get("proposed_action_counts") or {}
    wait_count = _action_count(action_counts, "wait")
    watch_count = _action_count(action_counts, "watch")
    buy_window_count = _action_count(action_counts, "buy_window")
    total = max(wait_count + watch_count + buy_window_count, 1)
    fallback_count = int(metadata_counts.get("fallback_review", 0) or 0) if label != "active" else 0
    blocking_reasons = []
    reasons = []
    score = 0.75 if operational else 0.45
    if buy_window_count == 0:
        blocking_reasons.append("buy_window_count_is_zero")
        score -= 0.18
    if wait_count == total:
        blocking_reasons.append("all_cases_are_wait")
        score -= 0.18
    if fallback_count > 0:
        blocking_reasons.append("fallback_review_rules_present")
        score -= 0.18
    if label != "active":
        blocking_reasons.append("not_operational_threshold_set")
    if not blocking_reasons and operational:
        reasons.append("operational active threshold set")
    elif not reasons:
        reasons.append("insufficient evidence for certification")
    score = max(0.0, min(1.0, round(score, 4)))
    if blocking_reasons and not operational:
        level = "not_evaluable" if "buy_window_count_is_zero" in blocking_reasons else "low"
    elif score >= 0.7:
        level = "medium"
    else:
        level = "low"
    return {
        "level": level,
        "score": score,
        "reasons": reasons,
        "blocking_reasons": blocking_reasons,
        "data_coverage": "limited",
        "buy_window_count": buy_window_count,
        "watch_count": watch_count,
        "wait_count": wait_count,
        "fallback_review_count": fallback_count,
        "overblocked_count": int(summary.get("cases_where_proposed_increased_wait", 0) or 0),
        "beneficial_block_count": int(summary.get("cases_where_proposed_prevented_bad_buy_window", 0) or 0),
        "inconclusive_count": int(summary.get("inconclusive_count", 0) or 0),
        "normal_to_extreme_count": int(summary.get("risk_stage_changed_count", 0) or 0),
        "completed_4w_count": _completed_count(summary, "4w"),
        "completed_13w_count": _completed_count(summary, "13w"),
        "completed_26w_count": _completed_count(summary, "26w"),
        "completed_52w_count": _completed_count(summary, "52w"),
    }


def _completed_count(summary: dict[str, Any], horizon: str) -> int:
    metrics = summary.get("metrics") or {}
    count = 0
    for action_payload in metrics.values():
        horizons = action_payload.get("horizons", {}) if isinstance(action_payload, dict) else {}
        count += int((horizons.get(horizon) or {}).get("count", 0) or 0)
    return count


def _action_count(action_counts: dict[str, Any], action: str) -> int:
    value = action_counts.get(action, 0)
    if isinstance(value, dict):
        value = value.get("count", 0)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
