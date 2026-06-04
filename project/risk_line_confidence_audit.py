from __future__ import annotations

from typing import Any

from project.threshold_metadata import metadata_for_payload


def build_risk_line_confidence_audit(
    threshold_payload: dict[str, Any],
    risk_lines: dict[str, Any],
) -> dict[str, Any]:
    metadata = metadata_for_payload(threshold_payload)
    rules = list(metadata.get("rules") or [])
    counts = dict(metadata.get("counts") or {})
    source_counts = _count_by(rules, "source")
    confidence_counts = _count_by(rules, "confidence")
    return {
        "title": "危険ライン信頼度監査",
        "status": "display_only",
        "monitoring_scope": "us_global_risk_core",
        "monitoring_scope_label": "米国・グローバル中心の危険監視",
        "counts": counts,
        "source_counts": source_counts,
        "confidence_counts": confidence_counts,
        "fallback_review_rules": source_counts.get("fallback_review", 0),
        "low_precision_rules": confidence_counts.get("low", 0),
        "pass_rules": _pass_rule_count(rules),
        "final_action_isolated_rules": sum(1 for row in rules if not bool(row.get("allow_final_action"))),
        "dxy_role": {
            "symbol": "DX-Y.NYB",
            "role": "global_dollar_stress",
            "label": "米ドル指数は米国・グローバルのドル高ストレス確認に使います。",
            "separate_from": ["USDJPY=X", "EURJPY=X"],
        },
        "jpy_fx_role": {
            "symbols": ["USDJPY=X", "EURJPY=X"],
            "role": "japan_resident_fx_context",
            "label": "USDJPY/EURJPY は日本円で見た外貨建て資産の円換算影響確認に使います。",
            "separate_from": "DX-Y.NYB",
        },
        "composite_trigger_relationship": _composite_trigger_relationship(risk_lines),
        "current_trigger_path_types": _trigger_path_types(risk_lines),
        "must_not_affect_final_action": True,
        "must_not_change_threshold_json": True,
        "caveat": "この監査は閾値の採用理由と信頼度の表示確認であり、危険ライン判定や最終判断を変更しません。",
    }


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "-")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _pass_rule_count(rows: list[dict[str, Any]]) -> int:
    total = 0
    for row in rows:
        actual = (row.get("evidence") or {}).get("actual_value_check") or {}
        if actual.get("status") == "pass":
            total += 1
    return total


def _trigger_path_types(risk_lines: dict[str, Any]) -> list[str]:
    seen: list[str] = []
    for row in risk_lines.get("trigger_path", []) or []:
        item_type = str(row.get("type") or "-")
        if item_type not in seen:
            seen.append(item_type)
    return seen


def _composite_trigger_relationship(risk_lines: dict[str, Any]) -> str:
    composite_score = risk_lines.get("composite_risk_score")
    path_types = set(_trigger_path_types(risk_lines))
    if "composite_score" in path_types:
        return f"総合ストレス指数 {composite_score} は trigger path に含まれ、段階判定の補助根拠として表示されます。"
    return f"総合ストレス指数 {composite_score} は表示されますが、現在の trigger path は個別指標やoverlay中心です。"
