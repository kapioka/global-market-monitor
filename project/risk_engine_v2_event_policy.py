from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

EVENT_POLICY_VERSION = "risk_engine_v2_event_policy.v1"
RETENTION_POLICY_VERSION = "risk_engine_v2_retention_policy.v1"


def build_event_policy(*, generated_at: str | None = None) -> dict[str, Any]:
    policy = {
        "policy_version": EVENT_POLICY_VERSION,
        "retention_policy_version": RETENTION_POLICY_VERSION,
        "generated_at": generated_at or datetime.now(UTC).isoformat(timespec="seconds"),
        "primary_benchmark": "ACWI",
        "fallback_benchmark_policy": "do_not_silently_fallback",
        "material_drawdown_threshold": -0.08,
        "drawdown_onset_rule": "first_decline_after_running_peak",
        "first_crossing_rule": "first_date_drawdown_from_peak_lte_threshold",
        "recovery_rule": "price_recovers_to_or_above_event_peak",
        "maximum_unresolved_event_horizon_days": 365,
        "event_merge_gap_days": 0,
        "pre_event_signal_lookback_days": 91,
        "post_cross_confirmation_grace_days": 91,
        "alert_only_outcome_horizon_days": 91,
        "event_split_anchor_rule": "event_anchor_date",
        "validation_start_date": "2024-03-15",
        "holdout_start_date": "2025-05-23",
        "boundary_purge_embargo_days": 91,
        "same_day_confirmed_signal_is_protective": True,
        "classification_precedence": [
            "insufficient_outcome",
            "protective",
            "late_confirmation",
            "missed_risk",
            "over_warning",
            "ambiguous",
        ],
        "event_id_generation": {
            "material_drawdown": "event:{policy_version}:{benchmark_id}:material:{peak_date}:{first_material_crossing_date}",
            "alert_only": "event:{policy_version}:{benchmark_id}:alert:{signal_start_date}:{signal_end_date}",
        },
        "retention_invariant": {
            "canonical_weekly_timeline_replaced_by_events": False,
            "event_records_reference_weekly_record_ids": True,
            "raw_values_duplicated_into_events": False,
            "raw_normalized_weekly_current_state_must_be_preserved": True,
        },
        "vintage_semantics": {
            "point_in_time_date_aligned": True,
            "vintage_locked": False,
            "revision_risk": "present",
            "vintage_source": "latest_observation_not_vintage_locked",
            "strictness_basis": "date_aligned_non_vintage",
        },
        "correlated_evidence_defaults": {
            "independent_vote_eligible": False,
            "score_impact": "diagnostic_metadata_only",
        },
        "processing_contract": {
            "maximum_unresolved_event_horizon_days": "used_for_censoring_not_ownership_end",
            "event_merge_gap_days": "used_for_confirmed_alert_and_candidate_segment_merging",
            "post_cross_confirmation_grace_days": "used_for_late_confirmation_classification",
            "boundary_purge_embargo_days": "used_for_fixed_date_split_purge_and_embargo",
        },
    }
    policy["policy_hash"] = policy_hash(policy)
    return policy


def policy_hash(policy: dict[str, Any]) -> str:
    payload = {key: value for key, value in policy.items() if key not in {"policy_hash", "generated_at"}}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_event_policy(policy: dict[str, Any]) -> None:
    required = {
        "policy_version",
        "primary_benchmark",
        "material_drawdown_threshold",
        "pre_event_signal_lookback_days",
        "post_cross_confirmation_grace_days",
        "validation_start_date",
        "holdout_start_date",
        "boundary_purge_embargo_days",
        "classification_precedence",
        "event_id_generation",
        "retention_invariant",
        "vintage_semantics",
        "policy_hash",
    }
    missing = sorted(required.difference(policy))
    if missing:
        raise ValueError(f"event policy missing required fields: {missing}")
    precedence = list(policy.get("classification_precedence") or [])
    if len(precedence) != len(set(precedence)):
        raise ValueError("event policy classification precedence contains duplicates")
    if float(policy.get("material_drawdown_threshold", 0.0)) >= 0:
        raise ValueError("material drawdown threshold must be negative")
