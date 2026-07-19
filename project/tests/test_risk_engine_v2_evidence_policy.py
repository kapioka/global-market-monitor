from __future__ import annotations

from project.risk_engine_v2_evidence_policy import POLICY_VERSION, build_evidence_policy, policy_hash


def test_evidence_policy_hash_is_stable_across_generation_time() -> None:
    first = build_evidence_policy(generated_at="2026-06-23T00:00:00+00:00")
    second = build_evidence_policy(generated_at="2026-06-24T00:00:00+00:00")

    assert first["policy_version"] == POLICY_VERSION
    assert first["policy_hash"] == second["policy_hash"]
    assert first["policy_hash"] == policy_hash(first)


def test_evidence_policy_defines_primary_domain_groups() -> None:
    policy = build_evidence_policy(generated_at="2026-06-23T00:00:00+00:00")
    groups = {group["domain_id"]: group for group in policy["primary_domain_groups"]}

    assert groups["credit"]["all_of"] == ["FRED:BAMLH0A0HYM2", "FRED:BAMLC0A0CM"]
    assert groups["rates"]["all_of"] == ["FRED:DFII10", "FRED:T10YIE"]
    assert groups["rates"]["any_of"] == [["FRED:T10Y2Y", "FRED:T10Y3M"]]
    assert groups["usd_funding"]["any_of"] == [["FRED:NFCI"]]
    assert policy["performance_denominator_policy"]["exclude_pending"] is True
