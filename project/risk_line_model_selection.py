from __future__ import annotations

from typing import Any


TARGET_THRESHOLDS: dict[str, dict[str, float]] = {
    "warning_target": {"full_f1": 0.45, "split_f1": 0.2, "walk_f1": 0.18, "review_ratio": 0.72},
    "danger_target": {"full_f1": 0.35, "split_f1": 0.15, "walk_f1": 0.12, "review_ratio": 0.72},
    "extreme_target": {"full_f1": 0.22, "split_f1": 0.08, "walk_f1": 0.05, "review_ratio": 0.68},
}


def build_risk_line_model_selection(backtest_report: dict[str, Any]) -> dict[str, Any]:
    indicators: dict[str, Any] = {}
    decision_counts = {"adopt": 0, "review": 0, "reject": 0}
    for ticker, payload in backtest_report.get("indicators", {}).items():
        indicator_selection = _select_indicator_models(ticker, payload)
        indicators[ticker] = indicator_selection
        for target_payload in indicator_selection["targets"].values():
            decision = str(target_payload.get("decision", "reject"))
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
    return {
        "indicator_count": len(indicators),
        "targets": list(backtest_report.get("targets", [])),
        "decision_counts": decision_counts,
        "indicators": indicators,
    }


def _select_indicator_models(ticker: str, payload: dict[str, Any]) -> dict[str, Any]:
    target_results: dict[str, Any] = {}
    for target, summary in payload.get("targets", {}).items():
        best = summary.get("best")
        if not best:
            target_results[target] = {
                "decision": "reject",
                "reason": "no_candidate",
                "selected_model": None,
                "metrics": None,
            }
            continue
        split_summary = summary.get("time_splits", {})
        walk_forward = summary.get("walk_forward", {})
        target_results[target] = _decision_for_target(best, split_summary, walk_forward, target)
    return {
        "family": payload.get("family", "-"),
        "adverse_direction": payload.get("adverse_direction", "-"),
        "targets": target_results,
    }


def _decision_for_target(
    best: dict[str, Any],
    split_summary: dict[str, Any],
    walk_forward: dict[str, Any],
    target: str,
) -> dict[str, Any]:
    thresholds = TARGET_THRESHOLDS.get(target, TARGET_THRESHOLDS["danger_target"])
    full_f1 = float(best.get("f1", 0.0) or 0.0)
    split_f1 = float(split_summary.get("average_test_f1") or 0.0)
    walk_f1 = float(walk_forward.get("average_test_f1") or 0.0)

    if full_f1 >= thresholds["full_f1"] and split_f1 >= thresholds["split_f1"] and walk_f1 >= thresholds["walk_f1"]:
        decision = "adopt"
        reason = "stable_enough"
    elif full_f1 >= thresholds["full_f1"] * thresholds.get("review_ratio", 0.75) and (
        split_f1 >= thresholds["split_f1"] * thresholds.get("review_ratio", 0.75)
        or walk_f1 >= thresholds["walk_f1"] * thresholds.get("review_ratio", 0.75)
    ):
        decision = "review"
        reason = "promising_but_unstable"
    else:
        decision = "reject"
        reason = "insufficient_out_of_sample"

    return {
        "decision": decision,
        "reason": reason,
        "selected_model": {
            "feature": best.get("feature"),
            "threshold": best.get("threshold"),
            "quantile": best.get("quantile"),
        },
        "metrics": {
            "full_f1": round(full_f1, 4),
            "split_f1": round(split_f1, 4),
            "walk_forward_f1": round(walk_f1, 4),
            "precision": best.get("precision"),
            "recall": best.get("recall"),
            "false_positive_rate": best.get("false_positive_rate"),
            "average_lead_weeks": best.get("average_lead_weeks"),
            "coverage": best.get("coverage"),
            "predicted_count": best.get("predicted_count"),
            "true_positive_count": best.get("true_positive_count"),
        },
        "selection_band": "core" if decision == "adopt" else ("fallback_candidate" if decision == "review" else "out_of_band"),
    }
