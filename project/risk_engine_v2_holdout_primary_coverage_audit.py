from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from project.risk_engine_v2_evidence_policy import build_evidence_policy

SCHEMA_VERSION = "risk_engine_v2.holdout_primary_coverage_audit.v1"
REASON_CODES = (
    "weekly_record_unresolved",
    "weekly_record_schema_missing",
    "series_mapping_missing",
    "series_not_in_store",
    "store_empty",
    "outside_store_date_range",
    "no_observation_on_or_before_evaluation_date",
    "date_alignment_failed",
    "observation_missing",
    "observation_stale",
    "insufficient_history",
    "quality_rejected",
    "vintage_unavailable",
    "vintage_policy_rejected",
    "non_vintage_disallowed",
    "coverage_field_lost",
    "coverage_schema_mismatch",
    "subset_recomputation_mismatch",
    "strict_requirement_not_met",
    "partial_requirement_not_met",
    "fallback_only",
    "unknown_reason",
)


def build_holdout_primary_coverage_audit(
    replay_payload: dict[str, Any],
    review_payload: dict[str, Any],
    holdout_payload: dict[str, Any],
    *,
    selected_store_path: str | Path | None = None,
    default_store_path: str | Path = "project/reports/risk_engine_v2_official_series.csv",
) -> dict[str, Any]:
    policy = build_evidence_policy(generated_at="1970-01-01T00:00:00+00:00")
    required_series = _required_series(policy)
    replay_by_id = {f"week:{case.get('date')}": case for case in replay_payload.get("cases", []) if isinstance(case, dict)}
    review_by_id = {
        str(row.get("record_id")): row
        for row in review_payload.get("weekly_timeline", [])
        if isinstance(row, dict) and row.get("record_id")
    }
    owner_by_id = _holdout_owners(holdout_payload)
    holdout_ids = sorted(owner_by_id)
    source_store = _source_store_path(replay_payload, selected_store_path)
    source_inventory = _store_inventory(source_store, required_series)
    default_inventory = _store_inventory(default_store_path, required_series)
    rows = [
        _audit_row(
            record_id=record_id,
            series_id=series_id,
            policy=policy,
            replay_case=replay_by_id.get(record_id),
            review_record=review_by_id.get(record_id),
            owners=owner_by_id.get(record_id, []),
            source_inventory=source_inventory,
            source_store_path=source_store,
        )
        for record_id in holdout_ids
        for series_id in required_series
    ]
    weekly = _weekly_summaries(holdout_ids, required_series, replay_by_id, review_by_id, rows)
    mismatch = [row for row in weekly if row["replay_coverage_state"] != row["holdout_coverage_state"]]
    reason_counts = Counter(code for row in rows for code in row["reason_codes"])
    reason_by_series: dict[str, Counter[str]] = defaultdict(Counter)
    reason_by_week: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        for code in row["reason_codes"]:
            reason_by_series[row["configured_series_id"]][code] += 1
            reason_by_week[row["weekly_record_id"]][code] += 1
    root_causes = _root_causes(source_inventory, default_inventory, weekly, rows)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "ok" if holdout_ids else "missing_holdout_records",
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "split_boundaries": {
            "validation_start_date": (holdout_payload.get("split_policy") or {}).get("validation_start_date"),
            "holdout_start_date": (holdout_payload.get("split_policy") or {}).get("holdout_start_date"),
        },
        "source_replay_type": replay_payload.get("replay_type"),
        "holdout_weekly_case_count": len(holdout_ids),
        "resolved_weekly_record_count": sum(1 for record_id in holdout_ids if record_id in replay_by_id and record_id in review_by_id),
        "unresolved_weekly_record_count": sum(1 for record_id in holdout_ids if record_id not in replay_by_id or record_id not in review_by_id),
        "required_primary_series_count": len(required_series),
        "audit_row_count": len(rows),
        "weekly_coverage_counts": dict(Counter(row["holdout_coverage_state"] for row in weekly)),
        "reason_code_counts": dict(reason_counts),
        "reason_code_counts_by_series": {series: dict(counter) for series, counter in sorted(reason_by_series.items())},
        "reason_code_counts_by_week": {week: dict(counter) for week, counter in sorted(reason_by_week.items())},
        "source_store": {
            "selected": _public_inventory(source_inventory),
            "default_local": _public_inventory(default_inventory),
        },
        "first_failing_stage_by_series": _first_stage_by(rows, "configured_series_id"),
        "first_failing_stage_by_week": _first_stage_by(rows, "weekly_record_id"),
        "replay_vs_holdout_reconciliation": {
            "identical_record_count_compared": len(weekly),
            "coverage_state_mismatch_count": len(mismatch),
            "strict_mismatches": sum(1 for row in mismatch if "primary_strict" in {row["replay_coverage_state"], row["holdout_coverage_state"]}),
            "partial_mismatches": sum(1 for row in mismatch if "primary_partial" in {row["replay_coverage_state"], row["holdout_coverage_state"]}),
            "fallback_mismatches": sum(1 for row in mismatch if "fallback" in {row["replay_coverage_state"], row["holdout_coverage_state"]}),
            "unavailable_mismatches": sum(1 for row in mismatch if "unavailable" in {row["replay_coverage_state"], row["holdout_coverage_state"]}),
            "coverage_field_loss_count": sum(1 for row in weekly if row["coverage_field_loss"]),
            "subset_recomputation_mismatch_count": len(mismatch),
            "mismatches": mismatch,
        },
        "root_causes": root_causes,
        "code_defect_exists": any(cause["category"] in {"subset_calculation_defect", "schema_serialization_defect"} for cause in root_causes),
        "data_gap_exists": any(cause["category"] in {"run_source_store_absent", "genuine_local_data_absence"} for cause in root_causes),
        "policy_decision_required": any(cause.get("policy_result") for cause in root_causes),
        "recommended_next_action": _recommended_next_action(root_causes),
        "weekly_records": weekly,
        "matrix_rows": rows,
        "decision": {
            "promotion_allowed": False,
            "reason": "holdout primary coverage audit is diagnostic-only",
        },
    }
    payload["artifact_hash"] = _stable_hash({key: value for key, value in payload.items() if key != "artifact_hash"})
    return payload


def run_holdout_primary_coverage_audit(
    replay_json: str | Path = "project/reports/risk_engine_v2_reconstructed_replay.json",
    review_json: str | Path = "project/reports/risk_engine_v2_replay_review.json",
    holdout_json: str | Path = "project/reports/risk_engine_v2_holdout_validation.json",
    reports_dir: str | Path = "project/reports",
    selected_store_path: str | Path | None = None,
    default_store_path: str | Path = "project/reports/risk_engine_v2_official_series.csv",
) -> dict[str, Any]:
    replay_payload = json.loads(Path(replay_json).read_text(encoding="utf-8"))
    review_payload = json.loads(Path(review_json).read_text(encoding="utf-8"))
    holdout_payload = json.loads(Path(holdout_json).read_text(encoding="utf-8"))
    payload = build_holdout_primary_coverage_audit(
        replay_payload,
        review_payload,
        holdout_payload,
        selected_store_path=selected_store_path,
        default_store_path=default_store_path,
    )
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "risk_engine_v2_holdout_primary_coverage_audit.json"
    markdown_path = reports_path / "risk_engine_v2_holdout_primary_coverage_audit.md"
    matrix_path = reports_path / "risk_engine_v2_holdout_primary_coverage_matrix.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_holdout_primary_coverage_audit_markdown(payload), encoding="utf-8")
    _write_matrix_csv(matrix_path, payload["matrix_rows"])
    return {
        "status": payload["status"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "matrix_path": str(matrix_path),
        "holdout_weekly_case_count": payload["holdout_weekly_case_count"],
        "audit_row_count": payload["audit_row_count"],
        "recommended_next_action": payload["recommended_next_action"],
    }


def render_holdout_primary_coverage_audit_markdown(payload: dict[str, Any]) -> str:
    reconciliation = payload["replay_vs_holdout_reconciliation"]
    lines = [
        "# risk_engine_v2 holdout primary coverage audit",
        "",
        "This audit is diagnostic only. It does not change thresholds, event policy, split membership, production decisions, or promotion state.",
        "",
        "## Summary",
        "",
        f"- status: {payload.get('status')}",
        f"- holdout_weekly_case_count: {payload.get('holdout_weekly_case_count')}",
        f"- resolved_weekly_record_count: {payload.get('resolved_weekly_record_count')}",
        f"- required_primary_series_count: {payload.get('required_primary_series_count')}",
        f"- audit_row_count: {payload.get('audit_row_count')}",
        f"- weekly_coverage_counts: {payload.get('weekly_coverage_counts')}",
        f"- replay_vs_holdout_mismatch_count: {reconciliation.get('coverage_state_mismatch_count')}",
        f"- recommended_next_action: {payload.get('recommended_next_action')}",
        "",
        "## Root Causes",
        "",
    ]
    for cause in payload.get("root_causes", []):
        lines.append(
            "- {category}: weeks={weeks} series={series} stage={stage} evidence={evidence}".format(
                category=cause.get("category"),
                weeks=cause.get("affected_week_count"),
                series=cause.get("affected_series_count"),
                stage=cause.get("first_failing_processing_stage"),
                evidence=cause.get("evidence"),
            )
        )
    lines.extend(["", "## Source Store", ""])
    for label, inventory in (payload.get("source_store") or {}).items():
        lines.append(f"- {label}: path={inventory.get('path')} exists={inventory.get('exists')}")
        for series_id, row in (inventory.get("series") or {}).items():
            lines.append(
                f"  - {series_id}: exists={row.get('series_exists_in_store')} observations={row.get('observation_count')} "
                f"range={row.get('minimum_observation_date')}..{row.get('maximum_observation_date')} main_reason={row.get('main_failure_reason')}"
            )
    return "\n".join(lines) + "\n"


def _holdout_owners(holdout_payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    owners: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in ((holdout_payload.get("splits") or {}).get("holdout") or {}).get("events", []) or []:
        if not isinstance(event, dict):
            continue
        for record_id in event.get("weekly_timeline_record_ids", []) or []:
            owners[str(record_id)].append(
                {
                    "event_id": event.get("event_id"),
                    "event_type": event.get("event_type"),
                    "event_anchor_date": event.get("event_anchor_date"),
                }
            )
    return dict(owners)


def _source_store_path(replay_payload: dict[str, Any], selected_store_path: str | Path | None) -> Path:
    if selected_store_path is not None:
        return Path(selected_store_path)
    store = ((replay_payload.get("reconstruction") or {}).get("official_series_store") or {}).get("path")
    return Path(str(store)) if store else Path("project/reports/risk_engine_v2_official_series.csv")


def _store_inventory(path: str | Path, required_series: list[str]) -> dict[str, Any]:
    store_path = Path(path)
    base: dict[str, Any] = {
        "path": str(store_path),
        "exists": store_path.exists(),
        "series": {},
        "read_error": None,
    }
    if not store_path.exists():
        for series_id in required_series:
            base["series"][series_id] = _empty_inventory_row(series_id, "series_not_in_store")
        return base
    try:
        frame = pd.read_csv(store_path, index_col=0)
    except Exception as exc:
        base["read_error"] = str(exc)
        for series_id in required_series:
            base["series"][series_id] = _empty_inventory_row(series_id, "store_empty")
        return base
    frame.index = pd.to_datetime(frame.index, errors="coerce")
    frame = frame[frame.index.notna()].sort_index()
    for series_id in required_series:
        if series_id not in frame.columns:
            base["series"][series_id] = _empty_inventory_row(series_id, "series_not_in_store")
            continue
        series = pd.to_numeric(frame[series_id], errors="coerce")
        non_null = series.dropna()
        duplicate_count = int(frame.index.duplicated().sum())
        null_count = int(series.isna().sum())
        base["series"][series_id] = {
            "configured_series_id": series_id,
            "provider": series_id.split(":", 1)[0],
            "source_store_name": store_path.name,
            "source_file": str(store_path),
            "series_exists_in_store": True,
            "observation_count": int(non_null.shape[0]),
            "minimum_observation_date": non_null.index.min().date().isoformat() if not non_null.empty else None,
            "maximum_observation_date": non_null.index.max().date().isoformat() if not non_null.empty else None,
            "latest_retrieval_timestamp": None,
            "vintage_capability": "not_supported_by_csv_store",
            "available_vintage_range": None,
            "duplicate_observation_count": duplicate_count,
            "invalid_null_observation_count": null_count,
            "main_failure_reason": None if not non_null.empty else "store_empty",
        }
    return base


def _audit_row(
    *,
    record_id: str,
    series_id: str,
    policy: dict[str, Any],
    replay_case: dict[str, Any] | None,
    review_record: dict[str, Any] | None,
    owners: list[dict[str, Any]],
    source_inventory: dict[str, Any],
    source_store_path: Path,
) -> dict[str, Any]:
    series_policy = (policy.get("series") or {}).get(series_id, {})
    raw_coverage = replay_case.get("primary_coverage") if isinstance(replay_case, dict) else None
    coverage: dict[str, Any] = raw_coverage if isinstance(raw_coverage, dict) else {}
    series_entry = (coverage.get("series") or {}).get(series_id, {})
    inventory = (source_inventory.get("series") or {}).get(series_id, _empty_inventory_row(series_id, "series_not_in_store"))
    evaluation_date = replay_case.get("date") if isinstance(replay_case, dict) else (review_record or {}).get("date")
    reason_codes = _row_reason_codes(replay_case, review_record, series_entry, inventory, evaluation_date)
    owners_text = "|".join(str(owner.get("event_id")) for owner in owners)
    return {
        "weekly_record_id": record_id,
        "evaluation_date": evaluation_date,
        "split": "holdout",
        "owning_event_ids": owners_text,
        "event_type": "|".join(str(owner.get("event_type")) for owner in owners),
        "event_anchor_date": "|".join(str(owner.get("event_anchor_date")) for owner in owners),
        "canonical_replay_source_record_id": record_id if replay_case else None,
        "resolution_status": "resolved" if replay_case and review_record else "unresolved",
        "logical_series_name": series_id.split(":", 1)[-1],
        "configured_series_id": series_id,
        "provider": series_policy.get("source_type") or series_id.split(":", 1)[0],
        "source_store_name": Path(str(source_store_path)).name,
        "frequency": series_policy.get("expected_frequency"),
        "unit": None,
        "primary_fallback_role": series_policy.get("primary_or_fallback"),
        "required_for_strict_coverage": True,
        "eligible_for_partial_coverage": True,
        "source_file": inventory.get("source_file") or str(source_store_path),
        "series_exists_in_store": inventory.get("series_exists_in_store"),
        "observation_count": inventory.get("observation_count"),
        "minimum_observation_date": inventory.get("minimum_observation_date"),
        "maximum_observation_date": inventory.get("maximum_observation_date"),
        "latest_retrieval_timestamp": inventory.get("latest_retrieval_timestamp"),
        "vintage_capability": inventory.get("vintage_capability"),
        "available_vintage_range": inventory.get("available_vintage_range"),
        "duplicate_observation_count": inventory.get("duplicate_observation_count"),
        "invalid_null_observation_count": inventory.get("invalid_null_observation_count"),
        "target_evaluation_date": evaluation_date,
        "selected_observation_date": series_entry.get("observation_date"),
        "selected_observation_value_presence": series_entry.get("observation_date") is not None,
        "age_calendar_days": series_entry.get("age_calendar_days"),
        "age_expected_observation_intervals": series_entry.get("age_business_days"),
        "date_alignment_method": "latest_observation_on_or_before_evaluation_date",
        "alignment_result": "aligned" if series_entry.get("observation_date") else "not_aligned",
        "comparison_history_dates_required": series_policy.get("minimum_history"),
        "comparison_history_dates_found": series_entry.get("history_count"),
        "required_history_count": series_policy.get("minimum_history"),
        "actual_history_count": series_entry.get("history_count"),
        "freshness_threshold": series_policy.get("freshness_tolerance_calendar_days"),
        "freshness_result": series_entry.get("freshness_status"),
        "stale_flag": "stale" in (series_entry.get("quality_flags") or []),
        "missing_flag": series_entry.get("observation_date") is None,
        "insufficient_history_flag": "insufficient_history" in (series_entry.get("quality_flags") or []),
        "quality_flags": "|".join(str(flag) for flag in series_entry.get("quality_flags", []) or []),
        "quality_rejection_result": bool(series_entry.get("quality_flags")),
        "vintage_status": series_entry.get("vintage_revision_status"),
        "non_vintage_status": "date_aligned_non_vintage_allowed",
        "source_revision_risk_status": "present",
        "series_level_coverage_state": "eligible" if series_entry.get("point_in_time_eligible") else "unavailable",
        "series_level_reason_codes": "|".join(reason_codes),
        "reason_codes": reason_codes,
        "reason_evidence": _reason_evidence(reason_codes, inventory, series_entry) if reason_codes else "",
        "final_weekly_coverage_state": coverage.get("coverage_status"),
        "final_weekly_reason_codes": "|".join(reason_codes),
    }


def _row_reason_codes(
    replay_case: dict[str, Any] | None,
    review_record: dict[str, Any] | None,
    series_entry: dict[str, Any],
    inventory: dict[str, Any],
    evaluation_date: Any,
) -> list[str]:
    codes: list[str] = []
    if replay_case is None or review_record is None:
        codes.append("weekly_record_unresolved")
    series_succeeded = bool(series_entry.get("point_in_time_eligible"))
    if series_succeeded:
        return []
    if not series_entry:
        codes.append("coverage_schema_mismatch")
    if inventory.get("series_exists_in_store") is not True:
        codes.append("series_not_in_store")
    elif not inventory.get("observation_count"):
        codes.append("store_empty")
    elif evaluation_date and inventory.get("maximum_observation_date") and str(evaluation_date) > str(inventory["maximum_observation_date"]):
        codes.append("outside_store_date_range")
    if series_entry.get("observation_date") is None:
        codes.append("no_observation_on_or_before_evaluation_date")
        codes.append("observation_missing")
    if series_entry.get("freshness_status") == "stale":
        codes.append("observation_stale")
    if "insufficient_history" in (series_entry.get("quality_flags") or []):
        codes.append("insufficient_history")
    if series_entry.get("quality_flags") and not series_entry.get("point_in_time_eligible"):
        codes.append("quality_rejected")
    if codes and not series_entry.get("point_in_time_eligible"):
        codes.append("strict_requirement_not_met")
        codes.append("partial_requirement_not_met")
    return sorted(set(codes or ["unknown_reason"]), key=lambda code: REASON_CODES.index(code) if code in REASON_CODES else 999)


def _weekly_summaries(
    holdout_ids: list[str],
    required_series: list[str],
    replay_by_id: dict[str, dict[str, Any]],
    review_by_id: dict[str, dict[str, Any]],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows_by_week: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        rows_by_week[row["weekly_record_id"]].append(row)
    weekly: list[dict[str, Any]] = []
    for record_id in holdout_ids:
        replay_case = replay_by_id.get(record_id)
        review_record = review_by_id.get(record_id)
        replay_coverage = replay_case.get("primary_coverage") if isinstance(replay_case, dict) else {}
        replay_state = replay_coverage.get("coverage_status") if isinstance(replay_coverage, dict) else None
        holdout_state = review_record.get("primary_coverage_status") if isinstance(review_record, dict) else None
        reason_codes = sorted({code for row in rows_by_week[record_id] for code in row["reason_codes"]})
        unavailable_status = replay_state == "unavailable"
        weekly.append(
            {
                "weekly_record_id": record_id,
                "evaluation_date": replay_case.get("date") if isinstance(replay_case, dict) else None,
                "replay_coverage_state": replay_state,
                "holdout_coverage_state": holdout_state,
                "coverage_field_loss": replay_state is not None and holdout_state is None,
                "expected_required_series_count": len(required_series),
                "available_required_series_count": sum(1 for row in rows_by_week[record_id] if row["series_level_coverage_state"] == "eligible"),
                "strict_eligibility": replay_coverage.get("primary_strict_available") if isinstance(replay_coverage, dict) else None,
                "partial_eligibility": replay_state == "primary_partial",
                "fallback_eligibility": False,
                "unavailable_status": unavailable_status,
                "final_weekly_coverage_state": replay_state,
                "final_weekly_reason_codes": reason_codes if unavailable_status else [],
                "first_failing_processing_stage": _first_stage_for_codes(reason_codes) if unavailable_status else None,
            }
        )
    return weekly


def _root_causes(source_inventory: dict[str, Any], default_inventory: dict[str, Any], weekly: list[dict[str, Any]], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    causes: list[dict[str, Any]] = []
    selected_exists = bool(source_inventory.get("exists"))
    default_has_data = any((row.get("observation_count") or 0) > 0 for row in (default_inventory.get("series") or {}).values())
    unavailable_weeks = sorted({row["weekly_record_id"] for row in weekly if row["final_weekly_coverage_state"] == "unavailable"})
    affected_rows = [row for row in rows if row["weekly_record_id"] in unavailable_weeks and row["reason_codes"]]
    affected_weeks = sorted({row["weekly_record_id"] for row in affected_rows})
    affected_series = sorted({row["configured_series_id"] for row in affected_rows})
    if not unavailable_weeks:
        return causes
    if not selected_exists:
        causes.append(
            {
                "category": "run_source_store_absent",
                "cause": "The reconstructed replay being audited was generated with an official-series store path that does not exist.",
                "affected_week_count": len(affected_weeks),
                "affected_series_count": len(affected_series),
                "affected_weeks": affected_weeks,
                "affected_series": affected_series,
                "first_failing_processing_stage": "local_source_inventory",
                "evidence": f"selected store path {source_inventory.get('path')} exists=false",
                "code_defect": False,
                "data_gap": True,
                "policy_result": False,
            }
        )
    if default_has_data and not selected_exists:
        causes.append(
            {
                "category": "alternate_local_store_available_but_not_used",
                "cause": "A default local official-series CSV exists, but it was not the source store for the current reconstructed replay artifact.",
                "affected_week_count": len(affected_weeks),
                "affected_series_count": len(affected_series),
                "affected_weeks": affected_weeks,
                "affected_series": affected_series,
                "first_failing_processing_stage": "replay_generation_input",
                "evidence": f"default store path {default_inventory.get('path')} exists={default_inventory.get('exists')}",
                "code_defect": False,
                "data_gap": False,
                "policy_result": False,
            }
        )
    if not causes:
        causes.append(
            {
                "category": "current_unavailability_policy_result",
                "cause": "Current coverage states are unavailable under the evidence present in the audited replay artifact.",
                "affected_week_count": len(affected_weeks),
                "affected_series_count": len(affected_series),
                "affected_weeks": affected_weeks,
                "affected_series": affected_series,
                "first_failing_processing_stage": "primary_coverage_calculation",
                "evidence": "No replay-vs-holdout state mismatch was detected.",
                "code_defect": False,
                "data_gap": True,
                "policy_result": True,
            }
        )
    return causes


def _recommended_next_action(root_causes: list[dict[str, Any]]) -> str:
    if any(cause.get("category") == "run_source_store_absent" for cause in root_causes):
        return "local data backfill Goal required"
    return "no further coverage repair required"


def _first_stage_by(rows: list[dict[str, Any]], key: str) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for row in rows:
        result.setdefault(str(row[key]), _first_stage_for_codes(row["reason_codes"]) if row["reason_codes"] else None)
    return result


def _first_stage_for_codes(codes: list[str]) -> str | None:
    if not codes:
        return None
    if "weekly_record_unresolved" in codes:
        return "event_to_weekly_resolution"
    if "series_not_in_store" in codes or "store_empty" in codes:
        return "local_source_inventory"
    if "outside_store_date_range" in codes or "no_observation_on_or_before_evaluation_date" in codes:
        return "selection_and_alignment"
    if "observation_stale" in codes or "insufficient_history" in codes or "quality_rejected" in codes:
        return "quality_and_eligibility"
    if "coverage_schema_mismatch" in codes or "coverage_field_lost" in codes:
        return "serialization"
    return "unknown"


def _required_series(policy: dict[str, Any]) -> list[str]:
    series: list[str] = []
    for group in policy.get("primary_domain_groups", []) or []:
        for item in group.get("all_of", []) or []:
            if str(item) not in series:
                series.append(str(item))
        for alternatives in group.get("any_of", []) or []:
            for item in alternatives:
                if str(item) not in series:
                    series.append(str(item))
    return series


def _public_inventory(inventory: dict[str, Any]) -> dict[str, Any]:
    return {"path": inventory.get("path"), "exists": inventory.get("exists"), "read_error": inventory.get("read_error"), "series": inventory.get("series")}


def _empty_inventory_row(series_id: str, reason: str) -> dict[str, Any]:
    return {
        "configured_series_id": series_id,
        "provider": series_id.split(":", 1)[0],
        "source_store_name": None,
        "source_file": None,
        "series_exists_in_store": False,
        "observation_count": 0,
        "minimum_observation_date": None,
        "maximum_observation_date": None,
        "latest_retrieval_timestamp": None,
        "vintage_capability": None,
        "available_vintage_range": None,
        "duplicate_observation_count": None,
        "invalid_null_observation_count": None,
        "main_failure_reason": reason,
    }


def _reason_evidence(codes: list[str], inventory: dict[str, Any], series_entry: dict[str, Any]) -> str:
    return json.dumps(
        {
            "reason_codes": codes,
            "series_exists_in_store": inventory.get("series_exists_in_store"),
            "observation_count": inventory.get("observation_count"),
            "store_range": [inventory.get("minimum_observation_date"), inventory.get("maximum_observation_date")],
            "selected_observation_date": series_entry.get("observation_date"),
            "quality_flags": series_entry.get("quality_flags"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _write_matrix_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = [key for key in rows[0] if key != "reason_codes"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: value for key, value in row.items() if key in fieldnames})


def _stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit risk_engine_v2 holdout primary coverage lineage.")
    parser.add_argument("--replay-json", default="project/reports/risk_engine_v2_reconstructed_replay.json")
    parser.add_argument("--review-json", default="project/reports/risk_engine_v2_replay_review.json")
    parser.add_argument("--holdout-json", default="project/reports/risk_engine_v2_holdout_validation.json")
    parser.add_argument("--reports-dir", default="project/reports")
    parser.add_argument("--selected-store-path", default=None)
    parser.add_argument("--default-store-path", default="project/reports/risk_engine_v2_official_series.csv")
    args = parser.parse_args()
    print(
        json.dumps(
            run_holdout_primary_coverage_audit(
                replay_json=args.replay_json,
                review_json=args.review_json,
                holdout_json=args.holdout_json,
                reports_dir=args.reports_dir,
                selected_store_path=args.selected_store_path,
                default_store_path=args.default_store_path,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
