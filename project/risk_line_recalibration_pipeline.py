from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from project.config_loader import load_config
from project.risk_line_reality_check_report import build_risk_line_reality_checked_report_from_config
from project.risk_line_threshold_store import (
    ACTIVE_THRESHOLDS_PATH,
    PROPOSED_THRESHOLDS_PATH,
    build_threshold_diff,
    build_threshold_payload_from_reality_check,
    load_threshold_payload,
    write_threshold_payload,
)


SUMMARY_JSON = "risk_line_recalibration_summary.json"
SUMMARY_MD = "risk_line_recalibration_summary.md"
DIFF_JSON = "risk_line_threshold_diff.json"
DIFF_MD = "risk_line_threshold_diff.md"


def write_risk_line_recalibration_outputs(config_path: str | Path, sample_only: bool = False) -> dict[str, Path]:
    config = load_config(config_path)
    reports_dir = Path(config["paths"]["reports_dir"])
    reports_dir.mkdir(parents=True, exist_ok=True)
    payload = build_risk_line_recalibration_payload(config, sample_only=sample_only)

    summary_json = reports_dir / SUMMARY_JSON
    summary_md = reports_dir / SUMMARY_MD
    diff_json = reports_dir / DIFF_JSON
    diff_md = reports_dir / DIFF_MD

    summary_json.write_text(json.dumps(payload["summary"], ensure_ascii=False, indent=2), encoding="utf-8")
    summary_md.write_text(render_risk_line_recalibration_summary_markdown(payload["summary"]), encoding="utf-8")
    diff_json.write_text(json.dumps(payload["diff"], ensure_ascii=False, indent=2), encoding="utf-8")
    diff_md.write_text(render_risk_line_threshold_diff_markdown(payload["diff"]), encoding="utf-8")
    write_threshold_payload(PROPOSED_THRESHOLDS_PATH, payload["proposed_thresholds"])

    return {
        "summary_json": summary_json,
        "summary_md": summary_md,
        "diff_json": diff_json,
        "diff_md": diff_md,
        "proposed_json": PROPOSED_THRESHOLDS_PATH,
    }


def build_risk_line_recalibration_payload(config: dict[str, Any], sample_only: bool = False) -> dict[str, Any]:
    reality_check = build_risk_line_reality_checked_report_from_config(config, sample_only=sample_only)
    active_payload = load_threshold_payload(ACTIVE_THRESHOLDS_PATH)
    proposed_payload = build_threshold_payload_from_reality_check(reality_check, status="proposed")
    diff = build_threshold_diff(active_payload, proposed_payload)
    summary = {
        "data_source": reality_check.get("data_source"),
        "warnings": reality_check.get("warnings", []),
        "active_version": active_payload.get("threshold_set", {}).get("version"),
        "proposed_version": proposed_payload.get("threshold_set", {}).get("version"),
        "decision_counts": reality_check.get("decision_counts", {}),
        "active_indicator_count": len(active_payload.get("indicators", {})),
        "proposed_indicator_count": len(proposed_payload.get("indicators", {})),
        "diff_summary": diff.get("summary", {}),
        "reality_checked_report": reality_check,
    }
    return {
        "summary": summary,
        "diff": diff,
        "proposed_thresholds": proposed_payload,
    }


def render_risk_line_recalibration_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Risk Line Recalibration Summary",
        "",
        f"- データソース: {summary.get('data_source', '-')}",
        f"- active_version: {summary.get('active_version', '-')}",
        f"- proposed_version: {summary.get('proposed_version', '-')}",
        f"- active 指標数: {summary.get('active_indicator_count', 0)}",
        f"- proposed 指標数: {summary.get('proposed_indicator_count', 0)}",
        f"- decision_counts: adopt={summary.get('decision_counts', {}).get('adopt', 0)}, fallback_review={summary.get('decision_counts', {}).get('fallback_review', 0)}, fallback_guarded={summary.get('decision_counts', {}).get('fallback_guarded', 0)}",
        f"- diff_summary: added={summary.get('diff_summary', {}).get('added', 0)}, removed={summary.get('diff_summary', {}).get('removed', 0)}, changed={summary.get('diff_summary', {}).get('changed', 0)}, unchanged={summary.get('diff_summary', {}).get('unchanged', 0)}",
        f"- 警告: {', '.join(summary.get('warnings', [])) if summary.get('warnings') else 'なし'}",
    ]
    return "\n".join(lines) + "\n"


def render_risk_line_threshold_diff_markdown(diff: dict[str, Any]) -> str:
    lines = [
        "# Risk Line Threshold Diff",
        "",
        f"- active_version: {diff.get('active_version', '-')}",
        f"- proposed_version: {diff.get('proposed_version', '-')}",
        f"- summary: added={diff.get('summary', {}).get('added', 0)}, removed={diff.get('summary', {}).get('removed', 0)}, changed={diff.get('summary', {}).get('changed', 0)}, unchanged={diff.get('summary', {}).get('unchanged', 0)}",
    ]
    for row in diff.get("changes", []):
        lines.extend([
            "",
            f"## {row.get('ticker')} / {row.get('stage')}",
            f"- change_type: {row.get('change_type')}",
            f"- active: {_rule_text(row.get('active'))}",
            f"- proposed: {_rule_text(row.get('proposed'))}",
        ])
    return "\n".join(lines) + "\n"


def _rule_text(rule: dict[str, Any] | None) -> str:
    if not rule:
        return "-"
    return f"{rule.get('feature')} {rule.get('direction')} {rule.get('threshold')}"
