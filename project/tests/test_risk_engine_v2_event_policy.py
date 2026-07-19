from __future__ import annotations

from project.risk_engine_v2_event_policy import build_event_policy, validate_event_policy


def test_event_policy_is_versioned_and_hashed() -> None:
    first = build_event_policy(generated_at="2026-01-01T00:00:00+00:00")
    second = build_event_policy(generated_at="2026-06-01T00:00:00+00:00")

    assert first["policy_version"] == "risk_engine_v2_event_policy.v1"
    assert first["retention_policy_version"] == "risk_engine_v2_retention_policy.v1"
    assert first["policy_hash"] == second["policy_hash"]
    assert first["primary_benchmark"] == "ACWI"
    assert first["retention_invariant"]["canonical_weekly_timeline_replaced_by_events"] is False
    validate_event_policy(first)


def test_event_policy_records_non_vintage_strictness_basis() -> None:
    policy = build_event_policy()

    assert policy["vintage_semantics"]["point_in_time_date_aligned"] is True
    assert policy["vintage_semantics"]["vintage_locked"] is False
    assert policy["vintage_semantics"]["revision_risk"] == "present"
    assert policy["vintage_semantics"]["strictness_basis"] == "date_aligned_non_vintage"
