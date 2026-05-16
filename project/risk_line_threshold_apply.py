from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from project.risk_line_threshold_store import (
    ACTIVE_THRESHOLDS_PATH,
    PROPOSED_THRESHOLDS_PATH,
    _normalized_rule,
    build_threshold_diff,
    load_threshold_payload,
    write_threshold_payload,
)


APPLY_LOG_JSON = "risk_line_threshold_apply_log.json"


def apply_proposed_thresholds(
    reports_dir: str | Path,
    tickers: list[str] | None = None,
    stages: list[str] | None = None,
) -> dict[str, Any]:
    active = load_threshold_payload(ACTIVE_THRESHOLDS_PATH)
    proposed = load_threshold_payload(PROPOSED_THRESHOLDS_PATH)
    selection = _select_applicable_rules(proposed, tickers=tickers, stages=stages)
    if not selection["changes"]:
        result = {
            "applied": False,
            "reason": "no_applicable_thresholds",
            "active_version_before": active.get("threshold_set", {}).get("version"),
            "active_version_after": active.get("threshold_set", {}).get("version"),
            "applied_changes": [],
        }
        _write_apply_log(reports_dir, result)
        return result

    material_changes = _filter_material_changes(active, selection["changes"])
    if not material_changes:
        result = {
            "applied": False,
            "reason": "no_material_changes",
            "active_version_before": active.get("threshold_set", {}).get("version"),
            "active_version_after": active.get("threshold_set", {}).get("version"),
            "proposed_version": proposed.get("threshold_set", {}).get("version"),
            "applied_changes": [],
            "skipped_unchanged": selection["changes"],
        }
        _write_apply_log(reports_dir, result)
        return result

    updated = json.loads(json.dumps(active))
    for change in material_changes:
        ticker = change["ticker"]
        stage = change["stage"]
        rule = change["rule"]
        updated.setdefault("indicators", {}).setdefault(ticker, {"weight": 1.0, "thresholds": {}})
        updated["indicators"][ticker].setdefault("thresholds", {})[stage] = rule
    updated["threshold_set"]["version"] = datetime.now().strftime("%Y-%m-%d-active-%H%M%S")
    updated["threshold_set"]["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    updated["threshold_set"]["source_report"] = proposed.get("threshold_set", {}).get("source_report")
    updated["threshold_set"]["notes"] = "Applied from proposed thresholds after manual approval."
    write_threshold_payload(ACTIVE_THRESHOLDS_PATH, updated)

    result = {
        "applied": True,
        "reason": "applied_selected_proposed_thresholds",
        "active_version_before": active.get("threshold_set", {}).get("version"),
        "active_version_after": updated.get("threshold_set", {}).get("version"),
        "proposed_version": proposed.get("threshold_set", {}).get("version"),
        "applied_changes": material_changes,
        "skipped_unchanged": [change for change in selection["changes"] if change not in material_changes],
        "post_apply_diff": build_threshold_diff(updated, proposed),
    }
    _write_apply_log(reports_dir, result)
    return result


def _select_applicable_rules(
    proposed: dict[str, Any],
    tickers: list[str] | None = None,
    stages: list[str] | None = None,
) -> dict[str, Any]:
    ticker_filter = set(tickers or [])
    stage_filter = set(stages or [])
    changes: list[dict[str, Any]] = []
    for ticker, payload in proposed.get("indicators", {}).items():
        if ticker_filter and ticker not in ticker_filter:
            continue
        for stage, rule in (payload.get("thresholds") or {}).items():
            if stage_filter and stage not in stage_filter:
                continue
            if not rule.get("feature"):
                continue
            changes.append({"ticker": ticker, "stage": stage, "rule": rule})
    return {"changes": changes}


def _write_apply_log(reports_dir: str | Path, result: dict[str, Any]) -> Path:
    path = Path(reports_dir) / APPLY_LOG_JSON
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _filter_material_changes(active: dict[str, Any], changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    material: list[dict[str, Any]] = []
    for change in changes:
        ticker = change["ticker"]
        stage = change["stage"]
        active_rule = ((active.get("indicators", {}).get(ticker) or {}).get("thresholds", {}).get(stage))
        if _normalized_rule(active_rule) != _normalized_rule(change["rule"]):
            material.append(change)
    return material
