from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from project.risk_engine_v2_contract import attach_shadow_diagnostic_contract
from project.risk_engine_v2_event_resolver import resolve_event_weekly_records

TARGET_CLASSES = {"missed_risk", "late_confirmation"}
CAUSE_CODES = (
    "data_unavailable",
    "data_stale",
    "insufficient_history",
    "domain_feature_not_triggered",
    "domain_stage_below_threshold",
    "global_policy_suppressed",
    "persistence_delayed",
    "signal_after_drawdown",
    "outcome_classification_issue",
    "unmodeled_or_abrupt_shock",
    "undetermined",
)


def build_risk_engine_v2_root_cause_report(replay_payload: dict[str, Any], review_payload: dict[str, Any]) -> dict[str, Any]:
    replay_cases = {f"week:{case.get('date')}": case for case in replay_payload.get("cases", []) if isinstance(case, dict)}
    events = [event for event in review_payload.get("events", review_payload.get("episodes", [])) or [] if isinstance(event, dict)]
    weekly_timeline = review_payload.get("weekly_timeline") if isinstance(review_payload.get("weekly_timeline"), list) else []
    if not weekly_timeline:
        weekly_timeline = [
            {"record_id": record_id, "date": case.get("date"), "candidate_stage": case.get("domain_candidate_stage"), "confirmed_stage": case.get("domain_confirmed_stage")}
            for record_id, case in replay_cases.items()
        ]
    resolver = resolve_event_weekly_records(events, weekly_timeline)
    resolved_by_event = {str(row.get("event_id")): row for row in resolver.get("events", []) if isinstance(row, dict)}
    targets = [event for event in events if _is_target_event(event)]
    seen: set[str] = set()
    analyses = []
    duplicate_target_count = 0
    for event in targets:
        event_id = str(event.get("event_id") or event.get("episode_id"))
        if event_id in seen:
            duplicate_target_count += 1
            continue
        seen.add(event_id)
        resolved_records = resolved_by_event.get(str(event.get("event_id")), {}).get("records", [])
        replay_window = [replay_cases.get(str(record.get("record_id")), {}) for record in resolved_records if isinstance(record, dict)]
        if not replay_window:
            replay_window = [replay_cases.get(f"week:{date}", {}) for date in event.get("case_dates", []) or []]
        analyses.append(_analyze_event(event, replay_window))
    counts = Counter(code for analysis in analyses for code in analysis.get("cause_codes", []))
    payload = {
        "status": "ok" if analyses else "no_target_episodes",
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "source_replay_type": replay_payload.get("replay_type"),
        "schema_version": "risk_engine_v2.root_cause.v1",
        "target_event_count": len(analyses),
        "target_episode_count": len(analyses),
        "duplicate_target_count": duplicate_target_count,
        "cause_code_counts": dict(counts),
        "allowed_cause_codes": list(CAUSE_CODES),
        "holdout_use_status": "observed_holdout_used_for_diagnosis_not_tuning",
        "decision": {
            "promotion_allowed": False,
            "reason": "root-cause analysis is diagnostic only and does not tune model behavior",
        },
        "events": analyses,
        "episodes": analyses,
    }
    return attach_shadow_diagnostic_contract(payload, artifact_type="review")


def render_risk_engine_v2_root_cause_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# risk_engine_v2 root-cause analysis",
        "",
        "This diagnostic report does not change thresholds, persistence, final_action, or buy_readiness_score.",
        "",
        "## Summary",
        "",
        f"- status: {payload.get('status', '-')}",
        f"- target_episode_count: {payload.get('target_episode_count', 0)}",
        f"- cause_code_counts: {payload.get('cause_code_counts', {})}",
        f"- holdout_use_status: {payload.get('holdout_use_status', '-')}",
        "",
        "## Episodes",
        "",
    ]
    for episode in payload.get("episodes", []) or []:
        lines.extend(
            [
                f"### {episode.get('episode_id', '-')}",
                "",
                f"- classification: {episode.get('classification', '-')}",
                f"- signal_window: {episode.get('signal_start_date', '-')}..{episode.get('signal_end_date', '-')}",
                f"- first_material_drawdown_crossing_date: {episode.get('first_material_drawdown_crossing_date')}",
                f"- first_candidate_stress_date: {episode.get('first_candidate_stress_date')}",
                f"- first_confirmed_stress_date: {episode.get('first_confirmed_stress_date')}",
                f"- confirmation_status: {episode.get('confirmation_status')}",
                f"- cause_codes: {episode.get('cause_codes', [])}",
                f"- failed_conditions: {episode.get('failed_conditions', [])}",
                f"- remediation_category: {episode.get('remediation_category', '-')}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def run_risk_engine_v2_root_cause_report(
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
    replay_payload = json.loads(replay_path.read_text(encoding="utf-8"))
    review_payload = json.loads(review_path.read_text(encoding="utf-8"))
    payload = build_risk_engine_v2_root_cause_report(replay_payload, review_payload)
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "risk_engine_v2_root_cause.json"
    markdown_path = reports_path / "risk_engine_v2_root_cause.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_risk_engine_v2_root_cause_markdown(payload), encoding="utf-8")
    return {
        "status": payload.get("status"),
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "target_episode_count": payload.get("target_episode_count", 0),
        "cause_code_counts": payload.get("cause_code_counts", {}),
        "policy_status": payload.get("policy_status"),
        "affects_final_action": payload.get("affects_final_action"),
        "decision": payload.get("decision", {}),
    }


def _is_target_event(episode: dict[str, Any]) -> bool:
    classification = str(episode.get("primary_classification") or episode.get("classification") or "")
    if classification in TARGET_CLASSES:
        return True
    if classification == "ambiguous" and episode.get("material_adverse_outcome") is True:
        return True
    if classification == "ambiguous":
        return any(case.get("material_adverse_outcome") is True for case in episode.get("cases", []) if isinstance(case, dict))
    return False


def _analyze_event(episode: dict[str, Any], replay_window: list[dict[str, Any]]) -> dict[str, Any]:
    cause_codes = _cause_codes(episode, replay_window)
    return {
        "event_id": episode.get("event_id") or episode.get("episode_id"),
        "episode_id": episode.get("episode_id") or episode.get("event_id"),
        "primary_classification": episode.get("primary_classification") or episode.get("classification"),
        "classification": episode.get("primary_classification") or episode.get("classification"),
        "event_type": episode.get("event_type"),
        "anchor_date": episode.get("event_anchor_date"),
        "event_ownership_window": {
            "start_date": episode.get("start_date"),
            "end_date": episode.get("event_end_date") or episode.get("end_date"),
            "ownership_end_date": episode.get("ownership_end_date"),
            "recovery_date": episode.get("recovery_date"),
            "censor_date": episode.get("censor_date"),
        },
        "signal_start_date": episode.get("signal_start_date") or episode.get("start_date"),
        "signal_end_date": episode.get("signal_end_date") or episode.get("end_date"),
        "outcome_due_date": episode.get("outcome_due_date"),
        "outcome_maturity_status": episode.get("maturity_status") or episode.get("outcome_maturity_status"),
        "first_material_crossing": episode.get("first_material_crossing_date") or episode.get("first_material_drawdown_crossing_date"),
        "first_material_drawdown_crossing_date": episode.get("first_material_crossing_date") or episode.get("first_material_drawdown_crossing_date"),
        "first_candidate_warning": episode.get("first_candidate_warning_date") or episode.get("first_candidate_stress_date"),
        "first_candidate_stress_date": episode.get("first_candidate_warning_date") or episode.get("first_candidate_stress_date"),
        "first_confirmed_warning": episode.get("first_confirmed_warning_date") or episode.get("first_confirmed_stress_date"),
        "first_confirmed_stress_date": episode.get("first_confirmed_warning_date") or episode.get("first_confirmed_stress_date"),
        "confirmation_delay": episode.get("confirmation_delay_days") or episode.get("confirmation_delay_calendar_days"),
        "confirmation_delay_calendar_days": episode.get("confirmation_delay_days") or episode.get("confirmation_delay_calendar_days"),
        "candidate_lead_time_days": episode.get("candidate_lead_time_days"),
        "confirmed_lead_time_days": episode.get("confirmed_lead_time_days"),
        "confirmation_status": episode.get("confirmation_status"),
        "secondary_attributes": episode.get("secondary_attributes", []),
        "cause_codes": cause_codes,
        "failed_conditions": _failed_conditions(episode, replay_window),
        "domain_evidence_timeline": [_domain_snapshot(case) for case in replay_window],
        "domain_timeline": [_domain_snapshot(case) for case in replay_window],
        "primary_coverage_timeline": [_coverage_snapshot(case) for case in replay_window],
        "coverage_timeline": [_coverage_snapshot(case) for case in replay_window],
        "benchmark_drawdown_path": _episode_drawdown_path(episode),
        "remediation_category": _remediation_category(cause_codes),
    }


def _cause_codes(episode: dict[str, Any], replay_window: list[dict[str, Any]]) -> list[str]:
    codes: list[str] = []
    quality_flags = [flag for case in replay_window for row in case.get("domain_evidence", []) for flag in row.get("quality_flags", [])]
    if "source_unavailable" in quality_flags:
        codes.append("data_unavailable")
    if "stale" in quality_flags:
        codes.append("data_stale")
    if "insufficient_history" in quality_flags:
        codes.append("insufficient_history")
    has_data_quality = bool(codes)
    if _all_candidate_normal(replay_window) and _has_domain_evidence(replay_window):
        codes.append("domain_feature_not_triggered")
    if _has_stage_below_threshold_evidence(replay_window):
        codes.append("domain_stage_below_threshold")
    if _has_explicit_global_suppression(replay_window):
        codes.append("global_policy_suppressed")
    if str(episode.get("confirmation_status")) == "not_confirmed_within_horizon" or "confirmation_delayed" in episode.get("secondary_attributes", []):
        codes.append("persistence_delayed")
    lead = episode.get("confirmed_lead_time_days")
    if (lead is not None and int(lead) < 0) or "signal_after_drawdown" in episode.get("secondary_attributes", []):
        codes.append("signal_after_drawdown")
    if (episode.get("maturity_status") or episode.get("outcome_maturity_status")) not in {None, "mature"}:
        codes.append("outcome_classification_issue")
    if (
        (episode.get("first_material_crossing_date") or episode.get("first_material_drawdown_crossing_date"))
        and _all_candidate_normal(replay_window)
        and not has_data_quality
        and not _has_domain_evidence(replay_window)
    ):
        codes.append("unmodeled_or_abrupt_shock")
    return sorted(set(codes or ["undetermined"]), key=lambda code: CAUSE_CODES.index(code) if code in CAUSE_CODES else 999)


def _failed_conditions(episode: dict[str, Any], replay_window: list[dict[str, Any]]) -> list[str]:
    failed: list[str] = []
    if _all_candidate_normal(replay_window):
        failed.append("no candidate stress before adverse outcome")
    if _has_explicit_global_suppression(replay_window):
        failed.append("domain stress did not pass global candidate policy")
    if str(episode.get("confirmation_status")) == "not_confirmed_within_horizon":
        failed.append("candidate stress did not become confirmed within horizon")
    if episode.get("confirmed_lead_time_days") is not None and int(episode["confirmed_lead_time_days"]) < 0:
        failed.append("confirmed signal occurred after material drawdown crossing")
    if not failed:
        failed.append("no deterministic failed condition identified from exported evidence")
    return failed


def _domain_snapshot(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": case.get("date"),
        "candidate_stage": case.get("domain_candidate_stage"),
        "confirmed_stage": case.get("domain_confirmed_stage"),
        "global_policy": case.get("global_policy_evidence", {}),
        "domains": [
            {
                "domain_id": row.get("domain_id"),
                "candidate_stage": row.get("candidate_stage"),
                "stage_eligibility": row.get("stage_eligibility"),
                "primary_fallback_status": row.get("primary_fallback_status"),
                "quality_flags": row.get("quality_flags", []),
                "suppressed_contribution": row.get("suppressed_contribution"),
                "suppression_reason": row.get("suppression_reason"),
            }
            for row in case.get("domain_evidence", []) or []
        ],
    }


def _coverage_snapshot(case: dict[str, Any]) -> dict[str, Any]:
    raw_coverage = case.get("primary_coverage")
    coverage: dict[str, Any] = raw_coverage if isinstance(raw_coverage, dict) else {}
    return {
        "date": case.get("date"),
        "coverage_status": coverage.get("coverage_status"),
        "primary_strict_available": coverage.get("primary_strict_available"),
        "missing_primary_groups": coverage.get("missing_primary_groups", []),
        "primary_missing_series": coverage.get("primary_missing_series", []),
        "primary_stale_series": coverage.get("primary_stale_series", []),
        "primary_history_insufficient_series": coverage.get("primary_history_insufficient_series", []),
    }


def _episode_drawdown_path(episode: dict[str, Any]) -> list[dict[str, Any]]:
    paths = [
        point
        for case in episode.get("cases", []) or []
        if isinstance(case, dict)
        for point in case.get("drawdown_path_13w", []) or []
        if isinstance(point, dict)
    ]
    return sorted(paths, key=lambda row: str(row.get("date") or ""))


def _all_candidate_normal(replay_window: list[dict[str, Any]]) -> bool:
    return bool(replay_window) and all(str(case.get("domain_candidate_stage")) == "normal" for case in replay_window)


def _has_stressed_domain_but_global_normal(replay_window: list[dict[str, Any]]) -> bool:
    for case in replay_window:
        if str(case.get("domain_candidate_stage")) != "normal":
            continue
        if any(row.get("contributed_to_global_candidate") for row in case.get("domain_evidence", []) or []):
            return True
    return False


def _has_domain_evidence(replay_window: list[dict[str, Any]]) -> bool:
    return any(bool(case.get("domain_evidence")) for case in replay_window)


def _has_stage_below_threshold_evidence(replay_window: list[dict[str, Any]]) -> bool:
    for case in replay_window:
        for row in case.get("domain_evidence", []) or []:
            stage = str(row.get("candidate_stage") or row.get("confirmed_stage") or "normal")
            if stage == "normal" and (
                row.get("stage_eligibility") is True
                or row.get("score") is not None
                or row.get("threshold") is not None
                or row.get("threshold_evidence")
            ):
                return True
    return False


def _has_explicit_global_suppression(replay_window: list[dict[str, Any]]) -> bool:
    for case in replay_window:
        raw_global_policy = case.get("global_policy_evidence")
        global_policy: dict[str, Any] = raw_global_policy if isinstance(raw_global_policy, dict) else {}
        if global_policy.get("suppression_status") and global_policy.get("suppression_reason"):
            return True
        for row in case.get("domain_evidence", []) or []:
            if row.get("suppressed_contribution") is True and row.get("suppression_reason"):
                return True
    return False


def _remediation_category(cause_codes: list[str]) -> str:
    if any(code in cause_codes for code in ("data_unavailable", "data_stale", "insufficient_history")):
        return "data_quality_or_primary_coverage_review"
    if "global_policy_suppressed" in cause_codes:
        return "global_policy_review_only"
    if "persistence_delayed" in cause_codes:
        return "persistence_review_only"
    if "domain_feature_not_triggered" in cause_codes:
        return "domain_feature_coverage_review_only"
    if "signal_after_drawdown" in cause_codes:
        return "lead_time_review_only"
    return "manual_diagnostic_review"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate diagnostic risk_engine_v2 missed-risk root-cause report.")
    parser.add_argument("--replay-json", default="project/reports/risk_engine_v2_reconstructed_replay.json")
    parser.add_argument("--review-json", default="project/reports/risk_engine_v2_replay_review.json")
    parser.add_argument("--reports-dir", default="project/reports")
    args = parser.parse_args()
    print(
        json.dumps(
            run_risk_engine_v2_root_cause_report(args.replay_json, args.review_json, args.reports_dir),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
