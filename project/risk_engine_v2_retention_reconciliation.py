from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from project.risk_engine_v2_contract import attach_shadow_diagnostic_contract
from project.risk_engine_v2_event_resolver import resolve_event_weekly_records
from project.risk_engine_v2_event_policy import RETENTION_POLICY_VERSION


def build_retention_reconciliation(replay_payload: dict[str, Any], review_payload: dict[str, Any]) -> dict[str, Any]:
    cases = [case for case in replay_payload.get("cases", []) or [] if isinstance(case, dict)]
    raw_weekly = review_payload.get("weekly_timeline")
    weekly: list[dict[str, Any]] = [row for row in raw_weekly if isinstance(row, dict)] if isinstance(raw_weekly, list) else []
    raw_events = review_payload.get("events")
    events: list[dict[str, Any]] = [row for row in raw_events if isinstance(row, dict)] if isinstance(raw_events, list) else []
    resolver = resolve_event_weekly_records(events, weekly)
    case_dates = [str(case.get("date")) for case in cases if case.get("date")]
    weekly_dates = [str(row.get("date")) for row in weekly if isinstance(row, dict) and row.get("date")]
    duplicate_weekly_dates = sorted(date for date in set(weekly_dates) if weekly_dates.count(date) > 1)
    required_losses = {
        "raw_observation_loss": _count_loss(case_dates, weekly_dates),
        "normalized_value_feature_loss": _required_field_loss(cases, ("domain_candidate_stage", "domain_confirmed_stage")),
        "weekly_date_loss": _count_loss(case_dates, weekly_dates),
        "duplicate_weekly_dates": len(duplicate_weekly_dates),
        "current_state_required_field_loss": _required_field_loss(weekly, ("candidate_stage", "confirmed_stage")),
        "domain_evidence_required_field_loss": _domain_evidence_loss(cases),
        "provenance_loss": _required_field_loss(weekly, ("provenance_present",)),
        "freshness_loss": _required_field_loss(weekly, ("freshness_present",)),
        "quality_loss": _required_field_loss(weekly, ("quality_flags",)),
        "primary_fallback_coverage_field_loss": _required_field_loss(weekly, ("primary_coverage_status",)),
        "unresolved_event_record_references": int(resolver["unresolved_event_record_reference_count"]),
    }
    pass_required = all(value == 0 for value in required_losses.values())
    payload = {
        "status": "pass" if pass_required else "fail",
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "schema_version": "risk_engine_v2.retention_reconciliation.v1",
        "retention_policy_version": RETENTION_POLICY_VERSION,
        "source_replay_type": replay_payload.get("replay_type"),
        "raw_observation_count_before": len(cases),
        "raw_observation_count_after": len(weekly),
        "raw_observation_hash_before": _stable_hash(case_dates),
        "raw_observation_hash_after": _stable_hash(weekly_dates),
        "normalized_value_feature_count_before": sum(1 for case in cases for key in ("domain_candidate_stage", "domain_confirmed_stage") if key in case),
        "normalized_value_feature_count_after": sum(1 for row in weekly for key in ("candidate_stage", "confirmed_stage") if key in row),
        "canonical_weekly_record_count_before": len(cases),
        "canonical_weekly_record_count_after": len(weekly),
        "missing_weekly_dates": sorted(set(case_dates).difference(weekly_dates)),
        "duplicate_weekly_dates": duplicate_weekly_dates,
        "loss_counts": required_losses,
        "unresolved_event_to_weekly_record_references": resolver["unresolved"],
        "orphan_event_references": resolver["shared_record_ids"],
        "completeness_status": "complete" if pass_required else "incomplete",
        "decision": {"promotion_allowed": False, "reason": "retention reconciliation is diagnostic-only"},
    }
    return attach_shadow_diagnostic_contract(payload, artifact_type="review")


def run_retention_reconciliation(
    replay_json: str | Path = "project/reports/risk_engine_v2_reconstructed_replay.json",
    review_json: str | Path = "project/reports/risk_engine_v2_replay_review.json",
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    replay_path = Path(replay_json)
    review_path = Path(review_json)
    if not replay_path.exists():
        return {"status": "missing_replay", "replay_json": str(replay_path)}
    if not review_path.exists():
        return {"status": "missing_review", "review_json": str(review_path)}
    payload = build_retention_reconciliation(
        json.loads(replay_path.read_text(encoding="utf-8")),
        json.loads(review_path.read_text(encoding="utf-8")),
    )
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "risk_engine_v2_retention_reconciliation.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": payload["status"], "json_path": str(json_path), "loss_counts": payload["loss_counts"]}


def _count_loss(before: list[str], after: list[str]) -> int:
    return len(set(before).difference(after))


def _required_field_loss(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> int:
    return sum(1 for row in rows for field in fields if field not in row or row.get(field) is None)


def _domain_evidence_loss(cases: list[dict[str, Any]]) -> int:
    loss = 0
    for case in cases:
        evidence = case.get("domain_evidence")
        if not isinstance(evidence, list) or not evidence:
            loss += 1
            continue
        for row in evidence:
            if not isinstance(row, dict) or not row.get("domain_id"):
                loss += 1
    return loss


def _stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate risk_engine_v2 retention reconciliation JSON.")
    parser.add_argument("--replay-json", default="project/reports/risk_engine_v2_reconstructed_replay.json")
    parser.add_argument("--review-json", default="project/reports/risk_engine_v2_replay_review.json")
    parser.add_argument("--reports-dir", default="project/reports")
    args = parser.parse_args()
    print(json.dumps(run_retention_reconciliation(args.replay_json, args.review_json, args.reports_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
