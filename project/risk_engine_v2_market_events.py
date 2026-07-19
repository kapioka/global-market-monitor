from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from datetime import date, timedelta
from typing import Any

import pandas as pd

from project.risk_engine_v2_event_policy import build_event_policy, validate_event_policy

STRESSED_STAGES = {"warning", "danger", "extreme"}
RANK = {"normal": 0, "warning": 1, "danger": 2, "extreme": 3}
REVIEW_CLASSES = (
    "protective",
    "over_warning",
    "ambiguous",
    "missed_risk",
    "late_confirmation",
    "insufficient_outcome",
)


def build_market_event_review(replay_payload: dict[str, Any], old_review: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = build_event_policy(generated_at="1970-01-01T00:00:00+00:00")
    validate_event_policy(policy)
    cases = _canonical_cases(replay_payload)
    weekly_timeline = [_weekly_record(case, index) for index, case in enumerate(cases)]
    material_events = _material_drawdown_events(cases, weekly_timeline, policy)
    owned_dates = {date for event in material_events for date in event["weekly_timeline_record_ids"]}
    alert_events = _alert_only_events(cases, weekly_timeline, owned_dates, policy)
    candidate_segments = _candidate_only_segments(cases, owned_dates, policy)
    events = sorted(material_events + alert_events, key=lambda event: (str(event.get("event_anchor_date")), str(event.get("event_id"))))
    old_episodes = list((old_review or {}).get("episodes") or [])
    mapping = _old_episode_mapping(old_episodes, events)
    raw_counts = Counter(str(event.get("primary_classification")) for event in events)
    counts = {name: raw_counts.get(name, 0) for name in REVIEW_CLASSES}
    maturity_counts = Counter(str(event.get("maturity_status")) for event in events)
    payload = {
        "status": "ok" if events else "no_events",
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "source_replay_type": replay_payload.get("replay_type"),
        "review_level": "event",
        "schema_version": "risk_engine_v2.event_review.v1",
        "event_policy_version": policy["policy_version"],
        "event_policy_hash": policy["policy_hash"],
        "retention_policy_version": policy["retention_policy_version"],
        "weekly_timeline_count": len(weekly_timeline),
        "weekly_timeline_hash": _stable_hash(weekly_timeline),
        "event_count": len(events),
        "episode_count": len(events),
        "old_episode_count": len(old_episodes),
        "old_episode_event_mapping": mapping,
        "unmapped_old_episode_count": sum(1 for row in mapping if row.get("relationship") == "unmapped"),
        "counts": counts,
        "event_maturity": {
            "total_event_count": len(events),
            "mature_event_count": maturity_counts.get("mature", 0),
            "pending_event_count": maturity_counts.get("pending", 0),
            "insufficient_outcome_event_count": counts.get("insufficient_outcome", 0),
            "performance_denominator": sum(1 for event in events if event.get("performance_evaluable") is True),
        },
        "diagnostic_segments": candidate_segments,
        "diagnostic_segment_counts": dict(Counter(str(row.get("segment_type")) for row in candidate_segments)),
        "event_policy_usage": _event_policy_usage(policy),
        "integrity": _integrity(events, weekly_timeline, mapping),
        "weekly_timeline": weekly_timeline,
        "events": events,
        "episodes": events,
        "case_evidence": weekly_timeline,
        "decision": {
            "promotion_allowed": False,
            "reason": "event-first review is diagnostic-only and requires holdout validation",
        },
    }
    payload["artifact_hash"] = _stable_hash({key: value for key, value in payload.items() if key != "artifact_hash"})
    return payload


def _canonical_cases(replay_payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_reconstruction = replay_payload.get("reconstruction")
    reconstruction_end = raw_reconstruction.get("end_date") if isinstance(raw_reconstruction, dict) else None
    cases: list[dict[str, Any]] = []
    for case in replay_payload.get("cases", []) or []:
        if not isinstance(case, dict):
            continue
        copied = dict(case)
        if reconstruction_end:
            copied["_reconstruction_end_date"] = str(reconstruction_end)
        cases.append(copied)
    return sorted(cases, key=lambda row: str(row.get("date") or ""))


def _weekly_record(case: dict[str, Any], index: int) -> dict[str, Any]:
    record_id = f"week:{case.get('date')}"
    return {
        "record_id": record_id,
        "index": index,
        "date": case.get("date"),
        "candidate_stage": case.get("domain_candidate_stage"),
        "confirmed_stage": case.get("domain_confirmed_stage"),
        "persistence_episode_id": case.get("domain_persistence_episode_id"),
        "persistence_entry_rule": case.get("domain_persistence_entry_rule"),
        "persistence_gap_reset": case.get("domain_persistence_gap_reset"),
        "primary_coverage_status": (
            (case.get("primary_coverage") or {}).get("coverage_status") if isinstance(case.get("primary_coverage"), dict) else None
        ),
        "primary_strict_available": (
            (case.get("primary_coverage") or {}).get("primary_strict_available") if isinstance(case.get("primary_coverage"), dict) else None
        ),
        "domain_evidence_present": bool(case.get("domain_evidence")),
        "global_policy_evidence_present": bool(case.get("global_policy_evidence")),
        "provenance_present": bool(case.get("source_history") or case.get("generated_at")),
        "freshness_present": bool(case.get("primary_coverage")),
        "quality_flags": list(case.get("quality_flags") or []),
        "outcome_status": (case.get("outcome") or {}).get("status") if isinstance(case.get("outcome"), dict) else None,
    }


def _material_drawdown_events(
    cases: list[dict[str, Any]], weekly_timeline: list[dict[str, Any]], policy: dict[str, Any]
) -> list[dict[str, Any]]:
    prices = _price_path(cases)
    threshold = float(policy["material_drawdown_threshold"])
    events: list[dict[str, Any]] = []
    peak: dict[str, Any] | None = None
    active: dict[str, Any] | None = None
    for point in prices:
        if peak is None or float(point["price"]) >= float(peak["price"]):
            if active is None:
                peak = point
        if peak is None:
            peak = point
        drawdown = (float(point["price"]) / float(peak["price"])) - 1.0 if float(peak["price"]) else 0.0
        if active is None and drawdown <= threshold:
            active = {
                "peak": peak,
                "first_crossing": point,
                "maximum": point,
                "recovery": None,
            }
            continue
        if active is not None:
            active_dd = (float(point["price"]) / float(active["peak"]["price"])) - 1.0
            max_dd = (float(active["maximum"]["price"]) / float(active["peak"]["price"])) - 1.0
            if active_dd < max_dd:
                active["maximum"] = point
            if float(point["price"]) >= float(active["peak"]["price"]):
                active["recovery"] = point
                events.append(_material_event(active, cases, weekly_timeline, policy))
                peak = point
                active = None
    if active is not None:
        events.append(_material_event(active, cases, weekly_timeline, policy))
    return events


def _material_event(
    active: dict[str, Any],
    cases: list[dict[str, Any]],
    weekly_timeline: list[dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    peak = active["peak"]
    crossing = active["first_crossing"]
    maximum = active["maximum"]
    recovery = active.get("recovery")
    crossing_date = _parse_date(crossing["date"])
    if crossing_date is None:
        raise ValueError(f"invalid material crossing date: {crossing.get('date')}")
    lookback_start = _date_text(crossing_date - timedelta(days=int(policy["pre_event_signal_lookback_days"])))
    observed_through = _observed_through(cases)
    event_end = str(recovery["date"]) if recovery else str(observed_through or maximum["date"])
    maximum_horizon_date = _date_text(crossing_date + timedelta(days=int(policy["maximum_unresolved_event_horizon_days"])))
    censor_date = None
    if recovery is None and maximum_horizon_date is not None and event_end > maximum_horizon_date:
        censor_date = maximum_horizon_date
    if lookback_start is None:
        raise ValueError(f"invalid material lookback date: {crossing.get('date')}")
    timeline_cases = [case for case in cases if lookback_start <= str(case.get("date")) <= event_end]
    timeline_ids = [f"week:{case.get('date')}" for case in timeline_cases]
    event = {
        "event_id": _event_id(policy, "material_drawdown", str(peak["date"]), str(crossing["date"])),
        "event_type": "material_drawdown",
        "event_anchor_date": str(crossing["date"]),
        "start_date": str(timeline_cases[0].get("date")) if timeline_cases else str(crossing["date"]),
        "end_date": event_end,
        "case_count": len(timeline_cases),
        "case_dates": [str(case.get("date")) for case in timeline_cases],
        "benchmark_id": policy["primary_benchmark"],
        "benchmark_source": "reconstructed_replay_outcome_prices",
        "benchmark_quality": "date_aligned_non_vintage",
        "peak_date": str(peak["date"]),
        "peak_value": peak["price"],
        "drawdown_onset_date": _drawdown_onset_date(peak, crossing, cases),
        "first_material_crossing_date": str(crossing["date"]),
        "crossing_value": crossing["price"],
        "maximum_drawdown": round((float(maximum["price"]) / float(peak["price"])) - 1.0, 6),
        "maximum_drawdown_date": str(maximum["date"]),
        "recovery_date": str(recovery["date"]) if recovery else None,
        "recovery_status": "recovered" if recovery else "unrecovered",
        "event_end_date": event_end,
        "ownership_end_date": event_end,
        "observed_through_date": observed_through,
        "censor_date": censor_date,
        "censor_status": "censored_by_maximum_unresolved_event_horizon" if censor_date else ("open_at_latest_observation" if recovery is None else "not_censored"),
        "outcome_due_date": _date_text(crossing_date + timedelta(days=int(policy["alert_only_outcome_horizon_days"]))),
        "outcome_observed_through": observed_through,
        "weekly_timeline_start": timeline_ids[0] if timeline_ids else None,
        "weekly_timeline_end": timeline_ids[-1] if timeline_ids else None,
        "weekly_timeline_record_ids": timeline_ids,
        "policy_version": policy["policy_version"],
        "policy_hash": policy["policy_hash"],
        "vintage_semantics": policy["vintage_semantics"],
    }
    _attach_signal_association(event, timeline_cases, policy)
    _classify_event(event, timeline_cases, policy)
    return event


def _alert_only_events(
    cases: list[dict[str, Any]],
    weekly_timeline: list[dict[str, Any]],
    owned_record_ids: set[str],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    segment: list[dict[str, Any]] = []
    merge_gap = int(policy["event_merge_gap_days"])
    normal_gap = 0
    for case in cases:
        record_id = f"week:{case.get('date')}"
        confirmed = str(case.get("domain_confirmed_stage") or "normal")
        if record_id not in owned_record_ids and confirmed in STRESSED_STAGES:
            segment.append(case)
            normal_gap = 0
            continue
        if segment and record_id not in owned_record_ids and merge_gap > normal_gap:
            normal_gap += 1
            continue
        if segment:
            events.append(_alert_event(segment, cases, policy))
            segment = []
            normal_gap = 0
    if segment:
        events.append(_alert_event(segment, cases, policy))
    return events


def _candidate_only_segments(cases: list[dict[str, Any]], owned_record_ids: set[str], policy: dict[str, Any]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    segment: list[dict[str, Any]] = []
    merge_gap = int(policy["event_merge_gap_days"])
    normal_gap = 0
    for case in cases:
        record_id = f"week:{case.get('date')}"
        candidate = str(case.get("domain_candidate_stage") or "normal")
        confirmed = str(case.get("domain_confirmed_stage") or "normal")
        if record_id not in owned_record_ids and candidate in STRESSED_STAGES and confirmed not in STRESSED_STAGES:
            segment.append(case)
            normal_gap = 0
            continue
        if segment and record_id not in owned_record_ids and merge_gap > normal_gap:
            normal_gap += 1
            continue
        if segment:
            segments.append(_candidate_segment(segment, policy))
            segment = []
            normal_gap = 0
    if segment:
        segments.append(_candidate_segment(segment, policy))
    return segments


def _candidate_segment(segment: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    start = str(segment[0].get("date"))
    end = str(segment[-1].get("date"))
    return {
        "segment_id": _event_id(policy, "candidate_only", start, end),
        "segment_type": "candidate_only",
        "diagnostic_only": True,
        "performance_evaluable": False,
        "signal_start_date": start,
        "signal_end_date": end,
        "case_count": len(segment),
        "case_dates": [str(case.get("date")) for case in segment],
        "weekly_timeline_record_ids": [f"week:{case.get('date')}" for case in segment],
        "peak_candidate_stage": _peak_stage(case.get("domain_candidate_stage") for case in segment),
        "peak_confirmed_stage": _peak_stage(case.get("domain_confirmed_stage") for case in segment),
        "event_merge_gap_days": int(policy["event_merge_gap_days"]),
        "policy_version": policy["policy_version"],
        "reason": "candidate warning-or-higher without contiguous confirmed warning-or-higher",
    }


def _alert_event(segment: list[dict[str, Any]], all_cases: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    start = str(segment[0].get("date"))
    end = str(segment[-1].get("date"))
    end_date = _parse_date(end)
    if end_date is None:
        raise ValueError(f"invalid alert-only end date: {end}")
    due = _date_text(end_date + timedelta(days=int(policy["alert_only_outcome_horizon_days"])))
    observed = _observed_through(all_cases)
    max_forward = _min_many(_drawdown(case, "13w") for case in segment)
    event = {
        "event_id": _event_id(policy, "alert_only", start, end),
        "event_type": "alert_only",
        "event_anchor_date": start,
        "start_date": start,
        "end_date": end,
        "case_count": len(segment),
        "case_dates": [str(case.get("date")) for case in segment],
        "benchmark_id": policy["primary_benchmark"],
        "signal_start_date": start,
        "signal_end_date": end,
        "peak_confirmed_stage": _peak_stage(case.get("domain_confirmed_stage") for case in segment),
        "outcome_due_date": due,
        "outcome_observed_through": observed,
        "maximum_forward_drawdown": max_forward,
        "maximum_forward_drawdown_date": _first_case_date_with_drawdown(segment, max_forward),
        "weekly_timeline_record_ids": [f"week:{case.get('date')}" for case in segment],
        "policy_version": policy["policy_version"],
        "policy_hash": policy["policy_hash"],
        "vintage_semantics": policy["vintage_semantics"],
    }
    _attach_signal_association(event, segment, policy)
    _classify_event(event, segment, policy)
    return event


def _attach_signal_association(event: dict[str, Any], timeline_cases: list[dict[str, Any]], policy: dict[str, Any]) -> None:
    crossing = event.get("first_material_crossing_date")
    candidate_warning = _first_stage_date(timeline_cases, "domain_candidate_stage", "warning")
    candidate_danger = _first_stage_date(timeline_cases, "domain_candidate_stage", "danger")
    confirmed_warning = _first_stage_date(timeline_cases, "domain_confirmed_stage", "warning")
    confirmed_danger = _first_stage_date(timeline_cases, "domain_confirmed_stage", "danger")
    before_crossing = [case for case in timeline_cases if crossing is None or str(case.get("date")) <= str(crossing)]
    event.update(
        {
            "first_candidate_warning_date": candidate_warning,
            "first_candidate_danger_date": candidate_danger,
            "first_confirmed_warning_date": confirmed_warning,
            "first_confirmed_danger_date": confirmed_danger,
            "candidate_stage_at_crossing": _stage_at(timeline_cases, "domain_candidate_stage", crossing),
            "confirmed_stage_at_crossing": _stage_at(timeline_cases, "domain_confirmed_stage", crossing),
            "peak_candidate_stage_before_crossing": _peak_stage(case.get("domain_candidate_stage") for case in before_crossing),
            "peak_confirmed_stage_before_crossing": _peak_stage(case.get("domain_confirmed_stage") for case in before_crossing),
            "candidate_lead_time_days": _lead_days(candidate_warning, crossing),
            "confirmed_lead_time_days": _lead_days(confirmed_warning, crossing),
            "confirmation_delay_days": _lead_days(candidate_warning, confirmed_warning),
            "signal_state_after_crossing": _stage_after(timeline_cases, crossing),
            "signal_state_at_recovery": _stage_at(timeline_cases, "domain_confirmed_stage", event.get("recovery_date")),
            "primary_coverage_statuses": sorted({status for case in timeline_cases if (status := _coverage_status(case)) is not None}),
            "quality_flags": sorted(set(flag for case in timeline_cases for flag in case.get("quality_flags", []) or [])),
            "secondary_attributes": [],
        }
    )


def _classify_event(event: dict[str, Any], timeline_cases: list[dict[str, Any]], policy: dict[str, Any]) -> None:
    due = _parse_date(event.get("outcome_due_date"))
    observed = _parse_date(event.get("outcome_observed_through"))
    if observed is None or due is None or observed < due:
        event.update({"maturity_status": "pending", "performance_evaluable": False, "primary_classification": "insufficient_outcome"})
        _set_classification_aliases(event)
        return
    event["maturity_status"] = "mature"
    event["performance_evaluable"] = True
    if event["event_type"] == "alert_only":
        if _alert_benign(timeline_cases):
            event["primary_classification"] = "over_warning"
        else:
            event["primary_classification"] = "ambiguous"
        _set_classification_aliases(event)
        return
    crossing = str(event.get("first_material_crossing_date"))
    crossing_date = _parse_date(crossing)
    candidate_before = event.get("first_candidate_warning_date") and str(event["first_candidate_warning_date"]) <= crossing
    confirmed_segments = _stage_segments(timeline_cases, "domain_confirmed_stage")
    candidate_segments = _stage_segments(timeline_cases, "domain_candidate_stage")
    active_confirmed_segment = _active_segment_at(confirmed_segments, crossing)
    first_confirmed_after = _first_segment_start_after(confirmed_segments, crossing)
    confirmed_before = active_confirmed_segment is not None
    confirmed_after = first_confirmed_after is not None
    within_grace = False
    if crossing_date is not None and first_confirmed_after is not None:
        confirmed_after_date = _parse_date(first_confirmed_after)
        if confirmed_after_date is not None:
            within_grace = confirmed_after_date <= crossing_date + timedelta(days=int(policy["post_cross_confirmation_grace_days"]))
    attrs: list[str] = []
    stale_warning = event.get("first_confirmed_warning_date") and not confirmed_before and str(event["first_confirmed_warning_date"]) <= crossing
    if stale_warning:
        attrs.append("stale_warning_reset_before_crossing")
    if candidate_before and not confirmed_before:
        attrs.append("confirmation_delayed")
    if confirmed_after:
        attrs.append("later_confirmed")
        attrs.append("signal_after_drawdown")
    if confirmed_before:
        if candidate_before and str(event.get("first_candidate_warning_date")) < str(event.get("first_confirmed_warning_date")):
            attrs.append("confirmation_delayed")
        event["primary_classification"] = "protective"
    elif candidate_before and confirmed_after and within_grace:
        event["primary_classification"] = "late_confirmation"
    elif not candidate_before and not confirmed_before:
        event["primary_classification"] = "missed_risk"
    elif candidate_before and not within_grace:
        event["primary_classification"] = "missed_risk"
        attrs.append("confirmation_after_grace" if confirmed_after else "candidate_only_before_crossing")
    else:
        event["primary_classification"] = "ambiguous"
    event["confirmed_signal_segment_at_crossing"] = active_confirmed_segment
    event["candidate_signal_segment_at_crossing"] = _active_segment_at(candidate_segments, crossing)
    event["post_cross_confirmation_within_grace"] = within_grace
    event["secondary_attributes"] = sorted(set(attrs))
    _set_classification_aliases(event)


def _stage_segments(cases: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    segment: list[dict[str, Any]] = []
    for case in cases:
        stage = str(case.get(field) or "normal")
        if stage in STRESSED_STAGES:
            segment.append(case)
            continue
        if segment:
            segments.append(_stage_segment(segment, field))
            segment = []
    if segment:
        segments.append(_stage_segment(segment, field))
    return segments


def _stage_segment(segment: list[dict[str, Any]], field: str) -> dict[str, Any]:
    return {
        "field": field,
        "start_date": str(segment[0].get("date")),
        "end_date": str(segment[-1].get("date")),
        "weekly_timeline_record_ids": [f"week:{case.get('date')}" for case in segment],
        "peak_stage": _peak_stage(case.get(field) for case in segment),
    }


def _active_segment_at(segments: list[dict[str, Any]], target_date: str | None) -> dict[str, Any] | None:
    if target_date is None:
        return None
    for segment in segments:
        if str(segment["start_date"]) <= target_date <= str(segment["end_date"]):
            return segment
    return None


def _first_segment_start_after(segments: list[dict[str, Any]], target_date: str | None) -> str | None:
    if target_date is None:
        return None
    starts = [str(segment["start_date"]) for segment in segments if str(segment["start_date"]) > target_date]
    return min(starts) if starts else None


def _set_classification_aliases(event: dict[str, Any]) -> None:
    classification = str(event.get("primary_classification") or "ambiguous")
    event["classification"] = classification
    event["outcome_maturity_status"] = event.get("maturity_status")
    event["performance_status"] = "evaluable" if event.get("performance_evaluable") else "insufficient_outcome"


def _old_episode_mapping(old_episodes: list[dict[str, Any]], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for episode in old_episodes:
        dates = [str(date) for date in episode.get("case_dates", []) or []]
        matched = [
            event
            for event in events
            if set(dates).intersection(
                set(event.get("weekly_timeline_record_ids", []))
                | {str(rid).replace("week:", "") for rid in event.get("weekly_timeline_record_ids", [])}
            )
        ]
        if not matched:
            rows.append(
                {
                    "old_episode_id": episode.get("episode_id"),
                    "new_event_id": None,
                    "relationship": "unmapped",
                    "merged_reason": "no overlapping weekly record",
                    "old_classification": episode.get("classification"),
                    "new_primary_classification": None,
                    "secondary_attributes": [],
                }
            )
            continue
        for event in matched[:1]:
            rows.append(
                {
                    "old_episode_id": episode.get("episode_id"),
                    "new_event_id": event.get("event_id"),
                    "relationship": "merged_to_event",
                    "merged_reason": "overlapping weekly timeline records under event-first ownership",
                    "old_classification": episode.get("classification"),
                    "new_primary_classification": event.get("primary_classification"),
                    "secondary_attributes": event.get("secondary_attributes", []),
                }
            )
    return rows


def _integrity(events: list[dict[str, Any]], weekly_timeline: list[dict[str, Any]], mapping: list[dict[str, Any]]) -> dict[str, Any]:
    crossing_counts = Counter(
        str(event.get("first_material_crossing_date")) for event in events if event.get("first_material_crossing_date")
    )
    split_owner: Counter[str] = Counter()
    for event in events:
        for record_id in event.get("weekly_timeline_record_ids", []) or []:
            split_owner[str(record_id)] += 1
    return {
        "duplicate_material_crossing_count": sum(1 for count in crossing_counts.values() if count > 1),
        "duplicate_weekly_owner_count": sum(1 for count in split_owner.values() if count > 1),
        "primary_classification_duplicate_count": sum(1 for event in events if isinstance(event.get("primary_classification"), list)),
        "unmapped_old_episode_count": sum(1 for row in mapping if row.get("relationship") == "unmapped"),
        "unresolved_duplicate_drawdown_count": _unresolved_duplicate_drawdown_count(events),
        "alert_only_inside_unrecovered_drawdown_count": _alert_inside_unrecovered_drawdown_count(events),
        "weekly_timeline_record_count": len(weekly_timeline),
        "event_owned_weekly_record_count": len(split_owner),
        "unowned_weekly_record_count": len(weekly_timeline) - len(split_owner),
    }


def _unresolved_duplicate_drawdown_count(events: list[dict[str, Any]]) -> int:
    material = [event for event in events if event.get("event_type") == "material_drawdown"]
    duplicates = 0
    for index, event in enumerate(material):
        if event.get("recovery_date"):
            continue
        end = str(event.get("event_end_date") or "")
        for later in material[index + 1 :]:
            if str(later.get("event_anchor_date") or "") <= end:
                duplicates += 1
    return duplicates


def _alert_inside_unrecovered_drawdown_count(events: list[dict[str, Any]]) -> int:
    material = [event for event in events if event.get("event_type") == "material_drawdown" and not event.get("recovery_date")]
    alerts = [event for event in events if event.get("event_type") == "alert_only"]
    count = 0
    for alert in alerts:
        anchor = str(alert.get("event_anchor_date") or "")
        if any(str(event.get("first_material_crossing_date") or "") <= anchor <= str(event.get("event_end_date") or "") for event in material):
            count += 1
    return count


def _event_policy_usage(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "maximum_unresolved_event_horizon_days": {
            "value": policy["maximum_unresolved_event_horizon_days"],
            "status": "executed",
            "use": "unrecovered material events expose censor_date without ending ownership",
        },
        "event_merge_gap_days": {
            "value": policy["event_merge_gap_days"],
            "status": "executed",
            "use": "confirmed alert-only and candidate-only diagnostic segment construction",
        },
        "post_cross_confirmation_grace_days": {
            "value": policy["post_cross_confirmation_grace_days"],
            "status": "executed",
            "use": "late_confirmation classification after material crossing",
        },
        "boundary_purge_embargo_days": {
            "value": policy["boundary_purge_embargo_days"],
            "status": "executed_in_holdout_validation",
            "use": "fixed date split purge and embargo",
        },
    }


def _price_path(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points: dict[str, dict[str, Any]] = {}
    for case in cases:
        raw_outcome = case.get("outcome")
        outcome = raw_outcome if isinstance(raw_outcome, dict) else {}
        date_text = outcome.get("current_price_date") or case.get("date")
        price = outcome.get("current_price")
        if date_text and price is not None:
            points[str(date_text)] = {"date": str(date_text), "price": float(price)}
    return [points[key] for key in sorted(points)]


def _observed_through(cases: list[dict[str, Any]]) -> str | None:
    if not cases:
        return None
    latest = str(cases[-1].get("date"))
    reconstruction_end = cases[-1].get("_reconstruction_end_date")
    if reconstruction_end:
        return max(latest, str(reconstruction_end))
    return latest


def _event_id(policy: dict[str, Any], event_type: str, start: str, end: str) -> str:
    payload = f"{policy['policy_version']}|{policy['primary_benchmark']}|{event_type}|{start}|{end}"
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
    return f"event-{event_type}-{start}-{end}-{digest}"


def _stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    try:
        return pd.Timestamp(value).date()
    except Exception:
        return None


def _date_text(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _drawdown_onset_date(peak: dict[str, Any], crossing: dict[str, Any], cases: list[dict[str, Any]]) -> str:
    peak_date = str(peak["date"])
    for case in cases:
        date_text = str(case.get("date"))
        raw_outcome = case.get("outcome")
        outcome = raw_outcome if isinstance(raw_outcome, dict) else {}
        if peak_date <= date_text <= str(crossing["date"]) and outcome.get("current_price") is not None:
            if float(outcome["current_price"]) < float(peak["price"]):
                return date_text
    return str(crossing["date"])


def _first_stage_date(cases: list[dict[str, Any]], field: str, minimum_stage: str) -> str | None:
    minimum = RANK[minimum_stage]
    for case in cases:
        if RANK.get(str(case.get(field) or "normal"), 0) >= minimum:
            return str(case.get("date"))
    return None


def _stage_at(cases: list[dict[str, Any]], field: str, target_date: Any) -> str | None:
    if target_date is None:
        return None
    previous = None
    for case in cases:
        if str(case.get("date")) <= str(target_date):
            previous = str(case.get(field) or "normal")
    return previous


def _stage_after(cases: list[dict[str, Any]], target_date: Any) -> str | None:
    if target_date is None:
        return None
    after = [case for case in cases if str(case.get("date")) > str(target_date)]
    return str(after[0].get("domain_confirmed_stage") or "normal") if after else None


def _peak_stage(stages: Any) -> str:
    values = [str(stage or "normal") for stage in stages]
    return max(values or ["normal"], key=lambda stage: RANK.get(stage, 0))


def _lead_days(start: Any, end: Any) -> int | None:
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    if start_date is None or end_date is None:
        return None
    return int((end_date - start_date).days)


def _coverage_status(case: dict[str, Any]) -> str | None:
    raw_coverage = case.get("primary_coverage")
    coverage = raw_coverage if isinstance(raw_coverage, dict) else {}
    value = coverage.get("coverage_status")
    return str(value) if value is not None else None


def _drawdown(case: dict[str, Any], horizon: str) -> float | None:
    raw_outcome = case.get("outcome")
    outcome = raw_outcome if isinstance(raw_outcome, dict) else {}
    raw_max_drawdowns = outcome.get("max_drawdowns")
    max_drawdowns = raw_max_drawdowns if isinstance(raw_max_drawdowns, dict) else {}
    value = max_drawdowns.get(horizon)
    return float(value) if value is not None else None


def _min_many(values: Iterable[float | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    return min(present) if present else None


def _first_case_date_with_drawdown(cases: list[dict[str, Any]], value: float | None) -> str | None:
    if value is None:
        return None
    for case in cases:
        if _drawdown(case, "13w") == value:
            return str(case.get("date"))
    return None


def _alert_benign(cases: list[dict[str, Any]]) -> bool:
    returns: list[float | None] = []
    drawdowns_4w: list[float | None] = []
    drawdowns_13w: list[float | None] = []
    for case in cases:
        raw_outcome = case.get("outcome")
        outcome = raw_outcome if isinstance(raw_outcome, dict) else {}
        raw_forward = outcome.get("forward_returns")
        forward = raw_forward if isinstance(raw_forward, dict) else {}
        forward_return = forward.get("13w")
        returns.append(float(forward_return) if forward_return is not None else None)
        drawdowns_4w.append(_drawdown(case, "4w"))
        drawdowns_13w.append(_drawdown(case, "13w"))
    clean_returns = _present_floats(returns)
    clean_drawdowns_4w = _present_floats(drawdowns_4w)
    clean_drawdowns_13w = _present_floats(drawdowns_13w)
    if len(clean_returns) != len(returns) or len(clean_drawdowns_4w) != len(drawdowns_4w) or len(clean_drawdowns_13w) != len(drawdowns_13w):
        return False
    return min(clean_returns) > -0.05 and min(clean_drawdowns_4w) > -0.08 and min(clean_drawdowns_13w) > -0.08


def _present_floats(values: Iterable[float | None]) -> list[float]:
    return [float(value) for value in values if value is not None]
