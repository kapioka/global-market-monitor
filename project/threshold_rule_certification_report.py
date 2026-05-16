from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project.config_loader import load_config
from project.risk_line_threshold_store import ACTIVE_THRESHOLDS_PATH, PROPOSED_THRESHOLDS_PATH, load_threshold_payload
from project.threshold_rule_certification import certify_threshold_rules
from project.threshold_rule_evidence import build_rule_evidence
from project.threshold_rule_identity import identities_from_payloads


def build_threshold_rule_certification_report(
    reports_dir: str | Path,
    active_thresholds_path: str | Path = ACTIVE_THRESHOLDS_PATH,
    proposed_thresholds_path: str | Path = PROPOSED_THRESHOLDS_PATH,
) -> dict[str, Any]:
    reports_path = Path(reports_dir)
    active_payload = load_threshold_payload(active_thresholds_path)
    proposed_payload = load_threshold_payload(proposed_thresholds_path)
    identities = identities_from_payloads(active_payload=active_payload, proposed_payload=proposed_payload)
    changed_cases = _load_json(reports_path / "threshold_changed_cases.json")
    action_validation = _load_json(reports_path / "action_validation_summary.json")
    evidence = build_rule_evidence(identities, changed_cases, action_validation)
    certification = certify_threshold_rules(evidence)
    certification["evidence_summary"] = {
        "rule_count": evidence.get("rule_count", 0),
        "buy_window_count": evidence.get("buy_window_count", 0),
        "family_counts": evidence.get("family_counts", {}),
    }
    return certification


def write_threshold_rule_certification_report(
    reports_dir: str | Path,
    active_thresholds_path: str | Path = ACTIVE_THRESHOLDS_PATH,
    proposed_thresholds_path: str | Path = PROPOSED_THRESHOLDS_PATH,
) -> dict[str, Any]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    payload = build_threshold_rule_certification_report(reports_path, active_thresholds_path, proposed_thresholds_path)
    json_path = reports_path / "threshold_rule_certification.json"
    md_path = reports_path / "threshold_rule_certification.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_threshold_rule_certification_markdown(payload), encoding="utf-8")
    return {"status": "ok", "json_path": str(json_path), "markdown_path": str(md_path), "summary": payload.get("summary", {})}


def render_threshold_rule_certification_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") or {}
    lines = [
        "# Threshold Rule Certification",
        "",
        "## Summary",
        f"- certified rules: {summary.get('certified_count', 0)}",
        f"- conditional rules: {summary.get('conditional_count', 0)}",
        f"- diagnostic only rules: {summary.get('diagnostic_only_count', 0)}",
        f"- hold rules: {summary.get('hold_count', 0)}",
        f"- rejected rules: {summary.get('reject_count', 0)}",
        f"- not evaluable rules: {summary.get('not_evaluable_count', 0)}",
        f"- currently affects final action: {payload.get('currently_affects_final_action', False)}",
        "",
        "## Rules",
        "| rule_id | family | source | confidence | status | allowed usage | reason |",
        "| ------- | ------ | ------ | ---------- | ------ | ------------- | ------ |",
    ]
    for row in payload.get("rules", []):
        lines.append(
            "| {rule_id} | {family} | {source} | {confidence} | {status} | {usage} | {reason} |".format(
                rule_id=row.get("rule_id", "-"),
                family=row.get("family", "-"),
                source=row.get("source", "-"),
                confidence=row.get("confidence", "-"),
                status=row.get("certification_status", "-"),
                usage=", ".join(row.get("allowed_usage", [])) or "-",
                reason=", ".join(row.get("blocking_reasons", []) or row.get("reasons", [])) or "-",
            )
        )
    return "\n".join(lines) + "\n"


def load_threshold_rule_certification_summary(reports_dir: str | Path | None) -> dict[str, Any]:
    if not reports_dir:
        return _empty_summary("missing_reports_dir")
    path = Path(reports_dir) / "threshold_rule_certification.json"
    if not path.exists():
        return _empty_summary("threshold rule certification report has not been generated")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _empty_summary(f"threshold rule certification report could not be loaded: {exc}")


def _empty_summary(reason: str) -> dict[str, Any]:
    return {
        "status": "not_available",
        "reason": reason,
        "summary": {
            "certified_count": 0,
            "conditional_count": 0,
            "diagnostic_only_count": 0,
            "hold_count": 0,
            "reject_count": 0,
            "not_evaluable_count": 0,
        },
        "top_blocking_reasons": [],
        "overblocking_contributors": [],
        "certified_rules": [],
        "conditional_rules": [],
        "currently_affects_final_action": False,
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate rule-level threshold certification reports.")
    parser.add_argument("--config", default="project/config.yaml")
    parser.add_argument("--reports-dir", default=None)
    args = parser.parse_args()
    config = load_config(args.config)
    reports_dir = args.reports_dir or config["paths"]["reports_dir"]
    print(json.dumps(write_threshold_rule_certification_report(reports_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
