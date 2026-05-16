from __future__ import annotations

from collections import Counter
from typing import Any


def certify_threshold_rules(rule_evidence: dict[str, Any]) -> dict[str, Any]:
    rows = [certify_rule(row) for row in rule_evidence.get("rules", [])]
    counts = Counter(row["certification_status"] for row in rows)
    summary = {
        "certified_count": counts.get("certified", 0),
        "conditional_count": counts.get("conditional", 0),
        "diagnostic_only_count": counts.get("diagnostic_only", 0),
        "hold_count": counts.get("hold", 0),
        "reject_count": counts.get("reject", 0),
        "not_evaluable_count": counts.get("not_evaluable", 0),
    }
    return {
        "status": "ok",
        "summary": summary,
        "top_blocking_reasons": _top_blocking_reasons(rows),
        "overblocking_contributors": [row for row in rows if "overblocking_or_stage_jump" in row["blocking_reasons"]],
        "certified_rules": [row for row in rows if row["certification_status"] == "certified"],
        "conditional_rules": [row for row in rows if row["certification_status"] == "conditional"],
        "rules": rows,
        "currently_affects_final_action": False,
    }


def certify_rule(evidence: dict[str, Any]) -> dict[str, Any]:
    blocking: list[str] = []
    reasons: list[str] = []
    source = str(evidence.get("source") or "not_evaluable")
    confidence = str(evidence.get("confidence") or "not_evaluable")
    if source == "fallback_review":
        blocking.append("fallback_review")
    if confidence in {"low", "not_evaluable", "fallback_review"}:
        blocking.append(f"confidence_{confidence}")
    if int(evidence.get("buy_window_count", 0) or 0) == 0:
        blocking.append("buy_window_count_is_zero")
    if int(evidence.get("completed_13w_count", 0) or 0) == 0 and int(evidence.get("completed_26w_count", 0) or 0) == 0:
        blocking.append("insufficient_forward_return_evidence")
    if int(evidence.get("trigger_count", 0) or 0) == 0:
        blocking.append("no_trigger_evidence")
    if int(evidence.get("watch_to_wait_count", 0) or 0) > 0 or int(evidence.get("normal_to_extreme_count", 0) or 0) > 0:
        blocking.append("overblocking_or_stage_jump")
    if evidence.get("family") == "commodity_oil" and int(evidence.get("family_overlap_count", 0) or 0) > 0:
        blocking.append("oil_family_overlap")
    if int(evidence.get("inconclusive_count", 0) or 0) >= max(1, int(evidence.get("trigger_count", 0) or 0)):
        blocking.append("all_changed_cases_inconclusive")

    if not blocking and confidence == "high":
        status = "certified"
        level = "high"
        allowed_usage = ["diagnostic_report", "replay_only", "research_only"]
        reasons.append("high confidence rule with completed evidence")
    elif not blocking and confidence == "medium":
        status = "conditional"
        level = "medium"
        allowed_usage = ["diagnostic_report", "replay_only", "research_only"]
        reasons.append("medium confidence rule requires explicit future adoption before final action use")
    elif "fallback_review" in blocking:
        status = "diagnostic_only"
        level = "none"
        allowed_usage = ["diagnostic_report", "replay_only", "research_only"]
        reasons.append("fallback_review rules are isolated from final action")
    elif "overblocking_or_stage_jump" in blocking or "oil_family_overlap" in blocking:
        status = "reject"
        level = "low"
        allowed_usage = ["diagnostic_report", "research_only"]
        reasons.append("rule contributed to overblocking or unexplained stage jump")
    elif "no_trigger_evidence" in blocking or "insufficient_forward_return_evidence" in blocking:
        status = "not_evaluable"
        level = "none"
        allowed_usage = ["diagnostic_report", "research_only"]
        reasons.append("not enough completed historical evidence")
    else:
        status = "hold"
        level = "low"
        allowed_usage = ["diagnostic_report", "replay_only", "research_only"]
        reasons.append("hold for additional history")

    score = _score(status, blocking)
    return {
        **{k: v for k, v in evidence.items() if not k.startswith("_")},
        "certification_status": status,
        "certification_level": level,
        "score": score,
        "decision": status,
        "reasons": reasons,
        "blocking_reasons": sorted(set(blocking)),
        "allowed_usage": allowed_usage,
        "eligible_for_final_action": False,
        "eligible_for_future_final_action": status == "certified",
        "currently_affects_final_action": False,
    }


def _score(status: str, blocking: list[str]) -> float:
    base = {"certified": 0.9, "conditional": 0.65, "diagnostic_only": 0.35, "hold": 0.3, "reject": 0.15}.get(status, 0.0)
    return round(max(0.0, base - min(len(blocking), 5) * 0.03), 4)


def _top_blocking_reasons(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(reason for row in rows for reason in row.get("blocking_reasons", []))
    return [{"reason": reason, "count": count} for reason, count in counts.most_common(8)]
