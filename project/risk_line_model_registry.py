from __future__ import annotations

from typing import Any


def build_risk_line_model_registry(selection_report: dict[str, Any]) -> dict[str, Any]:
    live_models: dict[str, Any] = {}
    review_queue: dict[str, Any] = {}
    rejected_targets: dict[str, Any] = {}
    stage_coverage = {"warning_target": 0, "danger_target": 0, "extreme_target": 0}

    for ticker, payload in selection_report.get("indicators", {}).items():
        live_targets: dict[str, Any] = {}
        review_targets: dict[str, Any] = {}
        rejected: dict[str, Any] = {}
        for target, summary in payload.get("targets", {}).items():
            decision = str(summary.get("decision", "reject"))
            if decision == "adopt":
                model = _registry_entry(summary)
                live_targets[target] = model
                stage_coverage[target] = stage_coverage.get(target, 0) + 1
            elif decision == "review":
                review_targets[target] = _registry_entry(summary)
            else:
                rejected[target] = _registry_entry(summary)
        if live_targets:
            live_models[ticker] = {
                "family": payload.get("family", "-"),
                "adverse_direction": payload.get("adverse_direction", "-"),
                "targets": live_targets,
            }
        if review_targets:
            review_queue[ticker] = {
                "family": payload.get("family", "-"),
                "adverse_direction": payload.get("adverse_direction", "-"),
                "targets": review_targets,
            }
        if rejected:
            rejected_targets[ticker] = {
                "family": payload.get("family", "-"),
                "adverse_direction": payload.get("adverse_direction", "-"),
                "targets": rejected,
            }

    return {
        "indicator_count": selection_report.get("indicator_count", 0),
        "targets": list(selection_report.get("targets", [])),
        "decision_counts": dict(selection_report.get("decision_counts", {})),
        "stage_coverage": stage_coverage,
        "live_indicator_count": len(live_models),
        "live_models": live_models,
        "review_queue": review_queue,
        "rejected_targets": rejected_targets,
        "data_source": selection_report.get("data_source"),
        "warnings": list(selection_report.get("warnings", [])),
    }


def _registry_entry(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": summary.get("decision"),
        "reason": summary.get("reason"),
        "selected_model": dict(summary.get("selected_model") or {}),
        "metrics": dict(summary.get("metrics") or {}),
    }
