from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from project.threshold_rule_identity import build_rule_id


def build_rule_evidence(
    rule_identities: list[dict[str, Any]],
    changed_cases: dict[str, Any] | None = None,
    action_validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    changed_rows = (changed_cases or {}).get("cases") or []
    validation_summary = (action_validation or {}).get("action_summary") or {}
    evidence_by_id = {_row["rule_id"]: _base_evidence(_row) for _row in rule_identities}
    for case in changed_rows:
        classification = str(case.get("classification") or "inconclusive")
        forward_returns = case.get("forward_returns") or {}
        max_drawdowns = case.get("max_drawdowns") or {}
        for indicator in case.get("contributing_indicators") or []:
            ticker = str(indicator.get("ticker") or "")
            proposed_level = _threshold_type_from_level(indicator.get("proposed_level"))
            if not ticker or not proposed_level:
                continue
            rule_id = build_rule_id(ticker, proposed_level)
            if rule_id not in evidence_by_id:
                continue
            row = evidence_by_id[rule_id]
            row["trigger_count"] += 1
            row[f"{proposed_level}_count"] += 1
            row["changed_action_count"] += int(_action_changed(case))
            row["changed_stage_count"] += int(_stage_changed(case))
            row["normal_to_extreme_count"] += int(_normal_to_extreme(case))
            row["watch_to_wait_count"] += int(_watch_to_wait(case))
            row[f"{classification}_count"] += 1
            if row["source"] == "fallback_review":
                row["fallback_driven_count"] += 1
            if _family_overlap(case, row["family"]):
                row["family_overlap_count"] += 1
            _add_forward_metrics(row, forward_returns, max_drawdowns)
    buy_window_count = _action_count(validation_summary, "buy_window")
    for row in evidence_by_id.values():
        _finalize_forward_metrics(row)
        row["buy_window_count"] = buy_window_count
        if buy_window_count == 0:
            row.setdefault("evidence_limits", []).append("buy_window_count_is_zero")
    summary = Counter(row["family"] for row in evidence_by_id.values())
    return {
        "status": "ok",
        "rule_count": len(evidence_by_id),
        "buy_window_count": buy_window_count,
        "family_counts": dict(summary),
        "rules": list(evidence_by_id.values()),
    }


def _base_evidence(identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "rule_id": identity["rule_id"],
        "indicator": identity["indicator"],
        "family": identity["family"],
        "threshold_type": identity["threshold_type"],
        "source": identity.get("source", "not_evaluable"),
        "confidence": identity.get("confidence", "not_evaluable"),
        "trigger_count": 0,
        "warning_count": 0,
        "danger_count": 0,
        "extreme_count": 0,
        "changed_action_count": 0,
        "changed_stage_count": 0,
        "normal_to_extreme_count": 0,
        "watch_to_wait_count": 0,
        "beneficial_block_count": 0,
        "overblocked_count": 0,
        "inconclusive_count": 0,
        "completed_4w_count": 0,
        "completed_13w_count": 0,
        "completed_26w_count": 0,
        "completed_52w_count": 0,
        "mean_4w_return_after_trigger": None,
        "mean_13w_return_after_trigger": None,
        "mean_26w_return_after_trigger": None,
        "worst_max_drawdown_after_trigger": None,
        "family_overlap_count": 0,
        "fallback_driven_count": 0,
        "_returns": defaultdict(list),
        "_drawdowns": [],
    }


def _threshold_type_from_level(level: Any) -> str | None:
    value = str(level or "").strip()
    return value if value in {"warning", "danger", "extreme"} else None


def _action_changed(case: dict[str, Any]) -> bool:
    return ((case.get("active") or {}).get("final_action")) != ((case.get("proposed") or {}).get("final_action"))


def _stage_changed(case: dict[str, Any]) -> bool:
    return ((case.get("active") or {}).get("risk_stage")) != ((case.get("proposed") or {}).get("risk_stage"))


def _normal_to_extreme(case: dict[str, Any]) -> bool:
    return (case.get("active") or {}).get("risk_stage") == "normal" and (case.get("proposed") or {}).get(
        "risk_stage"
    ) == "extreme_danger_line_reached"


def _watch_to_wait(case: dict[str, Any]) -> bool:
    return (case.get("active") or {}).get("final_action") == "watch" and (case.get("proposed") or {}).get("final_action") == "wait"


def _family_overlap(case: dict[str, Any], family: str) -> bool:
    families = Counter(_family_for_ticker(str(row.get("ticker") or "")) for row in case.get("contributing_indicators") or [])
    return family != "unknown" and families.get(family, 0) > 1


def _family_for_ticker(ticker: str) -> str:
    from project.threshold_metadata import threshold_family

    return threshold_family(ticker)


def _add_forward_metrics(row: dict[str, Any], forward_returns: dict[str, Any], max_drawdowns: dict[str, Any]) -> None:
    for horizon in ("4w", "13w", "26w", "52w"):
        value = forward_returns.get(horizon)
        if isinstance(value, (int, float)):
            row[f"completed_{horizon}_count"] += 1
            row["_returns"][horizon].append(float(value))
    for value in max_drawdowns.values():
        if isinstance(value, (int, float)):
            row["_drawdowns"].append(float(value))


def _finalize_forward_metrics(row: dict[str, Any]) -> None:
    for horizon in ("4w", "13w", "26w"):
        values = row["_returns"].get(horizon, [])
        if values:
            row[f"mean_{horizon}_return_after_trigger"] = round(sum(values) / len(values), 6)
    if row["_drawdowns"]:
        row["worst_max_drawdown_after_trigger"] = round(min(row["_drawdowns"]), 6)
    row.pop("_returns", None)
    row.pop("_drawdowns", None)


def _action_count(summary: dict[str, Any], action: str) -> int:
    value = summary.get(action, 0)
    if isinstance(value, dict):
        value = value.get("count", 0)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
