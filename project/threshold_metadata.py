from __future__ import annotations

from typing import Any

FAMILY_BY_TICKER = {
    "SPY": "equity",
    "ACWI": "equity",
    "1306.T": "equity",
    "HYG": "credit",
    "LQD": "credit",
    "HYG/LQD": "credit",
    "^VIX": "volatility",
    "^MOVE": "volatility",
    "^TNX": "rates",
    "FRED:MORTGAGE30US": "rates",
    "CL=F": "commodity_oil",
    "BZ=F": "commodity_oil",
    "GC=F": "commodity_gold",
    "DX-Y.NYB": "fx",
    "USDJPY=X": "fx",
}

FINAL_ACTION_BLOCKING_CONFIDENCE = {"low", "not_evaluable", "fallback_review"}


def threshold_family(ticker: str) -> str:
    return FAMILY_BY_TICKER.get(ticker, "unknown")


def rule_metadata(ticker: str, stage: str, rule: dict[str, Any] | None, generated_at: str | None = None) -> dict[str, Any]:
    rule = dict(rule or {})
    source = _source_for_rule(rule)
    confidence = _confidence_for_rule(rule, source)
    allow_final_action = _allow_final_action(source, confidence)
    allow_extreme_stage = _allow_extreme_stage(stage, source, confidence)
    return {
        "indicator": ticker,
        "family": threshold_family(ticker),
        "threshold_type": stage,
        "value": rule.get("threshold"),
        "source": source,
        "confidence": confidence,
        "sample_count": _metric(rule, "predicted_count"),
        "completed_4w_count": 0,
        "completed_13w_count": 0,
        "completed_26w_count": 0,
        "completed_52w_count": 0,
        "review_status": str(rule.get("decision") or rule.get("selection_mode") or source),
        "allow_final_action": allow_final_action,
        "allow_extreme_stage": allow_extreme_stage,
        "generated_at": generated_at,
        "reason": _reason_for_rule(rule, source, confidence),
        "evidence": {
            "feature": rule.get("feature"),
            "direction": rule.get("direction"),
            "decision": rule.get("decision"),
            "selection_mode": rule.get("selection_mode"),
            "coverage_forced": bool(rule.get("coverage_forced", False)),
            "backtest_metrics": rule.get("backtest_metrics") or {},
            "actual_value_check": rule.get("actual_value_check") or {},
        },
    }


def annotate_threshold_payload(payload: dict[str, Any]) -> dict[str, Any]:
    annotated = dict(payload)
    threshold_set = dict(annotated.get("threshold_set") or {})
    generated_at = threshold_set.get("generated_at")
    indicators = {}
    for ticker, item in (annotated.get("indicators") or {}).items():
        item_copy = dict(item or {})
        thresholds = {}
        for stage, rule in (item_copy.get("thresholds") or {}).items():
            rule_copy = dict(rule or {})
            rule_copy.setdefault("metadata", rule_metadata(str(ticker), str(stage), rule_copy, str(generated_at) if generated_at else None))
            thresholds[str(stage)] = rule_copy
        item_copy["family"] = threshold_family(str(ticker))
        item_copy["thresholds"] = thresholds
        indicators[str(ticker)] = item_copy
    annotated["indicators"] = indicators
    return annotated


def metadata_for_payload(payload: dict[str, Any]) -> dict[str, Any]:
    annotated = annotate_threshold_payload(payload)
    rows = []
    for ticker, item in (annotated.get("indicators") or {}).items():
        for stage, rule in (item.get("thresholds") or {}).items():
            rows.append(dict(rule.get("metadata") or rule_metadata(str(ticker), str(stage), rule)))
    counts = {
        "total_rules": len(rows),
        "allow_final_action": sum(1 for row in rows if row.get("allow_final_action")),
        "allow_extreme_stage": sum(1 for row in rows if row.get("allow_extreme_stage")),
        "fallback_review": sum(1 for row in rows if row.get("source") == "fallback_review"),
        "not_evaluable": sum(1 for row in rows if row.get("confidence") == "not_evaluable"),
    }
    return {"counts": counts, "rules": rows}


def _source_for_rule(rule: dict[str, Any]) -> str:
    if rule.get("source"):
        return str(rule["source"])
    if rule.get("decision") == "fallback_review" or rule.get("selection_mode") == "fallback_review" or rule.get("coverage_forced"):
        return "fallback_review"
    if rule.get("decision") == "adopt":
        return "historical_quantile"
    if not rule:
        return "not_evaluable"
    return "not_evaluable"


def _confidence_for_rule(rule: dict[str, Any], source: str) -> str:
    if source == "fallback_review":
        return "fallback_review"
    if source in {"not_evaluable", "insufficient_data"}:
        return "not_evaluable"
    metrics = rule.get("backtest_metrics") or {}
    actual = rule.get("actual_value_check") or {}
    if rule.get("decision") == "adopt" and actual.get("status") == "pass" and float(metrics.get("precision", 0.0) or 0.0) >= 0.45:
        return "medium"
    if rule.get("decision") == "adopt":
        return "low"
    return "not_evaluable"


def _allow_final_action(source: str, confidence: str) -> bool:
    return source != "fallback_review" and confidence not in FINAL_ACTION_BLOCKING_CONFIDENCE


def _allow_extreme_stage(stage: str, source: str, confidence: str) -> bool:
    if stage != "extreme":
        return _allow_final_action(source, confidence)
    return source != "fallback_review" and confidence in {"high", "medium"}


def _metric(rule: dict[str, Any], key: str) -> int:
    metrics = rule.get("backtest_metrics") or {}
    try:
        return int(metrics.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _reason_for_rule(rule: dict[str, Any], source: str, confidence: str) -> str:
    if source == "fallback_review":
        return "fallback_review thresholds are diagnostic only and cannot affect final action."
    if confidence == "not_evaluable":
        return "insufficient completed forward-return evidence."
    if confidence == "low":
        return "weak evidence or review status prevents final-action use."
    return str(rule.get("reason") or "rule has reviewable historical evidence.")
