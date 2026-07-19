from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd

from project.risk_engine_v2_evidence_policy import build_evidence_policy


def evaluate_case_primary_coverage(
    prices: pd.DataFrame,
    evaluation_date: pd.Timestamp,
    *,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_policy = policy or build_evidence_policy()
    groups = list(evidence_policy.get("primary_domain_groups") or [])
    raw_series_policy = evidence_policy.get("series")
    series_policy: dict[str, Any] = raw_series_policy if isinstance(raw_series_policy, dict) else {}
    series_entries = {
        series_id: _series_entry(prices, pd.Timestamp(evaluation_date), series_id, series_policy.get(series_id, {}))
        for series_id in _required_series(groups)
    }
    group_results = [_group_result(group, series_entries) for group in groups]
    satisfied_groups = [row["domain_id"] for row in group_results if row["satisfied"]]
    missing_groups = [row["domain_id"] for row in group_results if not row["satisfied"]]
    unique_series = list(series_entries.values())
    eligible_series = [row for row in unique_series if row["point_in_time_eligible"]]
    primary_domain_coverage = round(len(satisfied_groups) / len(groups), 6) if groups else 0.0
    primary_series_coverage = round(len(eligible_series) / len(unique_series), 6) if unique_series else 0.0
    primary_strict_available = bool(groups and len(satisfied_groups) == len(groups))
    return {
        "schema_version": "risk_engine_v2.case_primary_coverage.v1",
        "policy_version": evidence_policy.get("policy_version"),
        "policy_hash": evidence_policy.get("policy_hash"),
        "evaluation_date": pd.Timestamp(evaluation_date).date().isoformat(),
        "coverage_status": "primary_strict" if primary_strict_available else ("primary_partial" if eligible_series else "unavailable"),
        "primary_strict_available": primary_strict_available,
        "primary_series_coverage": primary_series_coverage,
        "primary_domain_coverage": primary_domain_coverage,
        "required_primary_groups": group_results,
        "satisfied_primary_groups": satisfied_groups,
        "missing_primary_groups": missing_groups,
        "primary_present_series": [row["canonical_series_id"] for row in unique_series if row["observation_date"]],
        "primary_missing_series": [row["canonical_series_id"] for row in unique_series if not row["observation_date"]],
        "primary_stale_series": [row["canonical_series_id"] for row in unique_series if row["freshness_status"] == "stale"],
        "primary_history_insufficient_series": [
            row["canonical_series_id"] for row in unique_series if "insufficient_history" in row["quality_flags"]
        ],
        "primary_quality_rejected_series": [
            row["canonical_series_id"] for row in unique_series if row["quality_flags"] and not row["point_in_time_eligible"]
        ],
        "fallback_series_used": [],
        "coverage_limitations": _coverage_limitations(unique_series, group_results),
        "series": series_entries,
    }


def summarize_primary_coverage(cases: list[dict[str, Any]]) -> dict[str, Any]:
    coverages: list[dict[str, Any]] = []
    for case in cases:
        raw_coverage = case.get("primary_coverage")
        if isinstance(raw_coverage, dict):
            coverages.append(raw_coverage)
    strict = [row for row in coverages if row.get("primary_strict_available") is True]
    partial = [row for row in coverages if row.get("coverage_status") == "primary_partial"]
    unavailable = [row for row in coverages if row.get("coverage_status") == "unavailable"]
    domain_values = [float(row.get("primary_domain_coverage", 0.0) or 0.0) for row in coverages]
    missing_counter = Counter(series for row in coverages for series in row.get("primary_missing_series", []) or [])
    stale_counter = Counter(series for row in coverages for series in row.get("primary_stale_series", []) or [])
    return {
        "timeline_case_count": len(cases),
        "primary_strict_available_cases": len(strict),
        "primary_partial_cases": len(partial),
        "primary_unavailable_cases": len(unavailable),
        "average_primary_domain_coverage": round(sum(domain_values) / len(domain_values), 6) if domain_values else 0.0,
        "minimum_primary_domain_coverage": min(domain_values) if domain_values else 0.0,
        "primary_domain_coverage_summary_type": "average_and_minimum_distribution",
        "primary_domain_coverage_distribution": dict(Counter(str(value) for value in domain_values)),
        "common_missing_series": dict(missing_counter.most_common()),
        "common_stale_series": dict(stale_counter.most_common()),
        "first_primary_strict_date": strict[0].get("evaluation_date") if strict else None,
        "last_primary_strict_date": strict[-1].get("evaluation_date") if strict else None,
    }


def _required_series(groups: list[dict[str, Any]]) -> list[str]:
    series: list[str] = []
    for group in groups:
        for item in group.get("all_of", []) or []:
            if item not in series:
                series.append(str(item))
        for alternatives in group.get("any_of", []) or []:
            for item in alternatives:
                if item not in series:
                    series.append(str(item))
    return series


def _series_entry(
    prices: pd.DataFrame,
    evaluation_date: pd.Timestamp,
    series_id: str,
    policy: dict[str, Any],
) -> dict[str, Any]:
    eval_ts = pd.Timestamp(evaluation_date).normalize()
    tolerance = int(policy.get("freshness_tolerance_calendar_days", 10) or 10)
    minimum_history = int(policy.get("minimum_history", 52) or 52)
    if series_id not in prices.columns:
        return _empty_series_entry(series_id, eval_ts, policy, tolerance, minimum_history, ["source_unavailable"])
    usable = pd.to_numeric(prices.loc[prices.index <= eval_ts, series_id], errors="coerce").dropna()
    if usable.empty:
        return _empty_series_entry(series_id, eval_ts, policy, tolerance, minimum_history, ["source_unavailable"])
    observation_date = pd.Timestamp(usable.index[-1]).normalize()
    age_calendar_days = int((eval_ts.date() - observation_date.date()).days)
    age_business_days = max(0, len(pd.bdate_range(observation_date.date(), eval_ts.date())) - 1)
    history_count = int(len(usable))
    quality_flags: list[str] = []
    freshness_status = "fresh"
    if age_calendar_days > tolerance:
        freshness_status = "stale"
        quality_flags.append("stale")
    if history_count < minimum_history:
        quality_flags.append("insufficient_history")
    point_in_time_eligible = not quality_flags
    return {
        "canonical_series_id": series_id,
        "source_id": series_id.split(":", 1)[-1],
        "source_type": policy.get("source_type", "unknown"),
        "observation_date": observation_date.date().isoformat(),
        "evaluation_date": eval_ts.date().isoformat(),
        "age_calendar_days": age_calendar_days,
        "age_business_days": age_business_days,
        "expected_frequency": policy.get("expected_frequency", "unknown"),
        "freshness_status": freshness_status,
        "freshness_tolerance_calendar_days": tolerance,
        "history_count": history_count,
        "minimum_required_history": minimum_history,
        "quality_flags": quality_flags,
        "point_in_time_eligible": point_in_time_eligible,
        "used_by_domain": [],
        "primary_or_fallback": policy.get("primary_or_fallback", "primary"),
        "vintage_revision_status": policy.get("vintage_revision_status", "unknown"),
    }


def _empty_series_entry(
    series_id: str,
    evaluation_date: pd.Timestamp,
    policy: dict[str, Any],
    tolerance: int,
    minimum_history: int,
    quality_flags: list[str],
) -> dict[str, Any]:
    return {
        "canonical_series_id": series_id,
        "source_id": series_id.split(":", 1)[-1],
        "source_type": policy.get("source_type", "unknown"),
        "observation_date": None,
        "evaluation_date": evaluation_date.date().isoformat(),
        "age_calendar_days": None,
        "age_business_days": None,
        "expected_frequency": policy.get("expected_frequency", "unknown"),
        "freshness_status": "missing",
        "freshness_tolerance_calendar_days": tolerance,
        "history_count": 0,
        "minimum_required_history": minimum_history,
        "quality_flags": quality_flags,
        "point_in_time_eligible": False,
        "used_by_domain": [],
        "primary_or_fallback": policy.get("primary_or_fallback", "primary"),
        "vintage_revision_status": policy.get("vintage_revision_status", "unknown"),
    }


def _group_result(group: dict[str, Any], series_entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    domain_id = str(group.get("domain_id"))
    all_of = [str(item) for item in group.get("all_of", []) or []]
    any_of = [[str(item) for item in alternatives] for alternatives in group.get("any_of", []) or []]
    all_satisfied = all(series_entries[item]["point_in_time_eligible"] for item in all_of)
    any_satisfied = all(any(series_entries[item]["point_in_time_eligible"] for item in alternatives) for alternatives in any_of)
    used = [item for item in all_of if series_entries[item]["point_in_time_eligible"]]
    for alternatives in any_of:
        chosen = next((item for item in alternatives if series_entries[item]["point_in_time_eligible"]), None)
        if chosen:
            used.append(chosen)
    for item in used:
        series_entries[item]["used_by_domain"].append(domain_id)
    return {
        "domain_id": domain_id,
        "all_of": all_of,
        "any_of": any_of,
        "satisfied": bool(all_satisfied and any_satisfied),
        "used_primary_series": sorted(set(used)),
        "missing_or_rejected_series": [
            item
            for item in all_of + [alt for alternatives in any_of for alt in alternatives]
            if not series_entries[item]["point_in_time_eligible"]
        ],
    }


def _coverage_limitations(series_entries: list[dict[str, Any]], group_results: list[dict[str, Any]]) -> list[str]:
    limitations: list[str] = []
    if any(not row["observation_date"] for row in series_entries):
        limitations.append("one or more primary series are missing as of the evaluation date")
    if any("stale" in row["quality_flags"] for row in series_entries):
        limitations.append("one or more primary series are stale as of the evaluation date")
    if any("insufficient_history" in row["quality_flags"] for row in series_entries):
        limitations.append("one or more primary series lack required history")
    if any(not row["satisfied"] for row in group_results):
        limitations.append("one or more primary domain groups are not satisfied")
    return limitations
