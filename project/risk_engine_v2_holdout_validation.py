from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from project.risk_engine_v2_contract import attach_shadow_diagnostic_contract
from project.risk_engine_v2_event_policy import build_event_policy
from project.risk_engine_v2_event_resolver import resolve_event_weekly_records
from project.risk_engine_v2_promotion_gate import evaluate_risk_engine_v2_promotion_gate
from project.risk_engine_v2_replay_review import build_risk_engine_v2_replay_review


@dataclass(frozen=True)
class HoldoutSplitCriteria:
    train_ratio: float = 0.6
    validation_ratio: float = 0.2
    minimum_holdout_episodes: int = 5
    maximum_severe_missed_risk_rate: float = 0.0
    maximum_late_confirmation_rate: float = 0.2
    maximum_over_warning_rate: float = 0.35
    minimum_protective_episodes: int = 1
    validation_start_date: str = "2024-03-15"
    holdout_start_date: str = "2025-05-23"

    def to_dict(self) -> dict[str, Any]:
        return {
            "train_ratio": self.train_ratio,
            "validation_ratio": self.validation_ratio,
            "holdout_ratio": round(1.0 - self.train_ratio - self.validation_ratio, 6),
            "minimum_holdout_episodes": self.minimum_holdout_episodes,
            "maximum_severe_missed_risk_rate": self.maximum_severe_missed_risk_rate,
            "maximum_late_confirmation_rate": self.maximum_late_confirmation_rate,
            "maximum_over_warning_rate": self.maximum_over_warning_rate,
            "minimum_protective_episodes": self.minimum_protective_episodes,
            "validation_start_date": self.validation_start_date,
            "holdout_start_date": self.holdout_start_date,
        }


def build_risk_engine_v2_holdout_validation(
    replay_payload: dict[str, Any],
    review_payload: dict[str, Any] | None = None,
    *,
    criteria: HoldoutSplitCriteria | None = None,
) -> dict[str, Any]:
    split_criteria = criteria or HoldoutSplitCriteria()
    review = review_payload or build_risk_engine_v2_replay_review(replay_payload)
    policy = build_event_policy(generated_at="1970-01-01T00:00:00+00:00")
    if (
        split_criteria.validation_start_date != policy["validation_start_date"]
        or split_criteria.holdout_start_date != policy["holdout_start_date"]
    ):
        policy = {
            **policy,
            "validation_start_date": split_criteria.validation_start_date,
            "holdout_start_date": split_criteria.holdout_start_date,
        }
    events = sorted(list(review.get("events") or review.get("episodes") or []), key=lambda row: str(_event_anchor_date(row) or ""))
    weekly_timeline = _canonical_weekly_timeline(replay_payload, review)
    resolver = resolve_event_weekly_records(events, weekly_timeline)
    split_rows = _split_events(events, resolver, policy)
    raw_summary = replay_payload.get("summary")
    summary: dict[str, Any] = raw_summary if isinstance(raw_summary, dict) else {}
    holdout = split_rows["holdout"]
    holdout_coverage = _holdout_primary_coverage(_unique_resolved_records(holdout["events"]))
    strict_primary_available = bool(holdout_coverage["strict_count"])
    split_status = _split_status(
        holdout_episode_count=int(holdout["episode_count"]),
        minimum_holdout_episodes=split_criteria.minimum_holdout_episodes,
    )
    evidence_status = _evidence_status(strict_primary_available=strict_primary_available)
    performance = _performance_summary(holdout, split_criteria, summary)
    performance_status = str(performance["status"])
    holdout_status = _combined_holdout_status(split_status, evidence_status, performance_status)
    cadence_status = _cadence_status(replay_payload, summary)
    if cadence_status != "valid":
        holdout_status = "blocked_invalid_cadence"
        performance_status = "not_evaluated_invalid_cadence"
        performance = {**performance, "status": performance_status, "blockers": [cadence_status]}
    payload = {
        "status": "ok" if events else "missing_review_events",
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "source_replay_type": replay_payload.get("replay_type"),
        "validation_level": "frozen_time_split_holdout",
        "criteria": split_criteria.to_dict(),
        "split_policy": {
            "type": "fixed_calendar_date_purged_event_time_split",
            "purge_overlapping_outcome_windows": True,
            "split_basis": "event.event_anchor_date",
            "validation_start_date": policy["validation_start_date"],
            "holdout_start_date": policy["holdout_start_date"],
            "boundary_purge_embargo_days": policy["boundary_purge_embargo_days"],
            "anchor_rules": {
                "material_drawdown": "first_material_crossing_date",
                "alert_only": "signal_start_date",
            },
            "overlap_basis": "event ownership/evidence/outcome windows",
        },
        "event_weekly_resolution": {key: value for key, value in resolver.items() if key not in {"events", "unique_records"}},
        "cadence_status": cadence_status,
        "strict_primary_available": strict_primary_available,
        "split_boundaries": _split_boundaries(split_rows),
        "splits": split_rows,
        "holdout": {
            "status": holdout_status,
            "split_status": split_status,
            "evidence_status": evidence_status,
            "performance_status": performance_status,
            "event_count": holdout["event_count"],
            "episode_count": holdout["event_count"],
            "case_count": holdout["case_count"],
            "maturity": holdout["maturity"],
            "performance_denominator": holdout["performance_denominator"],
            "counts": holdout["counts"],
            "performance": performance,
            "reason": _holdout_reason(holdout_status),
        },
        "decision": {
            "promotion_allowed": False,
            "reason": "holdout validation is diagnostic-only; promotion remains blocked pending strict primary evidence and manual approval",
        },
    }
    gate = evaluate_risk_engine_v2_promotion_gate(replay_payload, review, holdout_payload=payload)
    payload["promotion_gate"] = gate
    payload["decision"] = {
        "promotion_allowed": False,
        "reason": gate["reason"],
    }
    return attach_shadow_diagnostic_contract(payload, artifact_type="holdout_validation")


def render_risk_engine_v2_holdout_validation_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# risk_engine_v2 holdout validation",
        "",
        "This validation is diagnostic only. It does not change final_action, buy_readiness_score, thresholds, or promotion state.",
        "",
        "## Summary",
        "",
        f"- status: {payload.get('status', '-')}",
        f"- source_replay_type: {payload.get('source_replay_type', '-')}",
        f"- validation_level: {payload.get('validation_level', '-')}",
        f"- policy_status: {payload.get('policy_status', '-')}",
        f"- affects_final_action: {payload.get('affects_final_action', False)}",
        f"- strict_primary_available: {payload.get('strict_primary_available', False)}",
        f"- holdout_status: {(payload.get('holdout') or {}).get('status', '-')}",
        f"- split_status: {(payload.get('holdout') or {}).get('split_status', '-')}",
        f"- evidence_status: {(payload.get('holdout') or {}).get('evidence_status', '-')}",
        f"- performance_status: {(payload.get('holdout') or {}).get('performance_status', '-')}",
        "",
        "## Split Criteria",
        "",
    ]
    for key, value in (payload.get("criteria") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Splits", ""])
    for name, split in (payload.get("splits") or {}).items():
        lines.append(
            "- {name}: episodes={episodes} cases={cases} purged_overlap={purged} start={start} end={end} counts={counts}".format(
                name=name,
                episodes=split.get("episode_count", 0),
                cases=split.get("case_count", 0),
                purged=split.get("purged_overlap_count", 0),
                start=split.get("start_date"),
                end=split.get("end_date"),
                counts=split.get("counts", {}),
            )
        )
    gate = payload.get("promotion_gate") or {}
    lines.extend(["", "## Promotion Gate", ""])
    lines.append(f"- status: {gate.get('status', '-')}")
    lines.append(f"- promotion_allowed: {gate.get('promotion_allowed', False)}")
    lines.append(f"- reason: {gate.get('reason', '-')}")
    for blocker in gate.get("blockers", []) or []:
        lines.append(f"- blocker: {blocker}")
    return "\n".join(lines) + "\n"


def run_risk_engine_v2_holdout_validation(
    replay_json: str | Path = "project/reports/risk_engine_v2_reconstructed_replay.json",
    review_json: str | Path = "project/reports/risk_engine_v2_replay_review.json",
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    replay_path = Path(replay_json)
    if not replay_path.exists():
        return {"status": "missing_replay", "replay_json": str(replay_path)}
    replay_payload = json.loads(replay_path.read_text(encoding="utf-8"))
    review_path = Path(review_json)
    review_payload = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else None
    payload = build_risk_engine_v2_holdout_validation(replay_payload, review_payload)
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "risk_engine_v2_holdout_validation.json"
    markdown_path = reports_path / "risk_engine_v2_holdout_validation.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_risk_engine_v2_holdout_validation_markdown(payload), encoding="utf-8")
    return {
        "status": payload.get("status"),
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "holdout_status": (payload.get("holdout") or {}).get("status"),
        "split_status": (payload.get("holdout") or {}).get("split_status"),
        "evidence_status": (payload.get("holdout") or {}).get("evidence_status"),
        "performance_status": (payload.get("holdout") or {}).get("performance_status"),
        "policy_status": payload.get("policy_status"),
        "affects_final_action": payload.get("affects_final_action"),
        "decision": payload.get("decision", {}),
    }


def _split_episodes(episodes: list[dict[str, Any]], criteria: HoldoutSplitCriteria) -> dict[str, dict[str, Any]]:
    total = len(episodes)
    train_end = int(total * criteria.train_ratio)
    validation_end = train_end + int(total * criteria.validation_ratio)
    train_base = episodes[:train_end]
    validation_base = episodes[train_end:validation_end]
    holdout = episodes[validation_end:]
    validation_start = str(validation_base[0].get("start_date")) if validation_base else None
    holdout_start = str(holdout[0].get("start_date")) if holdout else None
    train = _purge_overlapping_episodes(train_base, validation_start)
    validation = _purge_overlapping_episodes(validation_base, holdout_start)
    return {
        "train": _split_summary(train, purged_count=len(train_base) - len(train)),
        "validation": _split_summary(validation, purged_count=len(validation_base) - len(validation)),
        "holdout": _split_summary(holdout, purged_count=0),
    }


def _split_events(events: list[dict[str, Any]], resolver: dict[str, Any], policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    resolved_by_event = {str(row.get("event_id")): row for row in resolver.get("events", []) if isinstance(row, dict)}
    validation_start = str(policy["validation_start_date"])
    holdout_start = str(policy["holdout_start_date"])
    embargo_days = int(policy["boundary_purge_embargo_days"])
    split_bases: dict[str, list[dict[str, Any]]] = {"train": [], "validation": [], "holdout": []}
    excluded: list[dict[str, Any]] = []
    for event in events:
        anchor = _event_anchor_date(event)
        split_name = _split_name(anchor, validation_start, holdout_start)
        exclusion = _boundary_exclusion(event, split_name, validation_start, holdout_start, embargo_days)
        enriched = {**event, "_resolved_weekly_records": resolved_by_event.get(str(event.get("event_id")), {}).get("records", [])}
        if exclusion:
            excluded.append({**enriched, "split": split_name, "exclusion_reason": exclusion})
            continue
        split_bases[split_name].append(enriched)
    return {
        "train": _split_summary(
            split_bases["train"], purged_count=sum(1 for row in excluded if row["split"] == "train"), excluded=excluded
        ),
        "validation": _split_summary(
            split_bases["validation"],
            purged_count=sum(1 for row in excluded if row["split"] == "validation"),
            excluded=excluded,
        ),
        "holdout": _split_summary(
            split_bases["holdout"], purged_count=sum(1 for row in excluded if row["split"] == "holdout"), excluded=excluded
        ),
    }


def _purge_overlapping_episodes(episodes: list[dict[str, Any]], next_split_start: str | None) -> list[dict[str, Any]]:
    if not next_split_start:
        return episodes
    return [
        row for row in episodes if str(row.get("outcome_due_date") or row.get("end_date") or row.get("start_date") or "") < next_split_start
    ]


def _canonical_weekly_timeline(replay_payload: dict[str, Any], review_payload: dict[str, Any]) -> list[dict[str, Any]]:
    weekly = review_payload.get("weekly_timeline")
    if isinstance(weekly, list) and weekly:
        return [row for row in weekly if isinstance(row, dict)]
    records: list[dict[str, Any]] = []
    for index, case in enumerate(replay_payload.get("cases", []) or []):
        if not isinstance(case, dict):
            continue
        date_text = str(case.get("date") or "")
        if not date_text:
            continue
        raw_coverage = case.get("primary_coverage")
        coverage: dict[str, Any] = raw_coverage if isinstance(raw_coverage, dict) else {}
        records.append(
            {
                "record_id": f"week:{date_text}",
                "index": index,
                "date": date_text,
                "candidate_stage": case.get("domain_candidate_stage"),
                "confirmed_stage": case.get("domain_confirmed_stage"),
                "primary_coverage_status": coverage.get("coverage_status"),
                "primary_strict_available": coverage.get("primary_strict_available"),
                "quality_flags": list(case.get("quality_flags") or []),
            }
        )
    return records


def _event_anchor_date(event: dict[str, Any]) -> str | None:
    if event.get("event_anchor_date"):
        return str(event["event_anchor_date"])
    if event.get("event_type") == "material_drawdown" and event.get("first_material_crossing_date"):
        return str(event["first_material_crossing_date"])
    if event.get("event_type") == "alert_only" and event.get("signal_start_date"):
        return str(event["signal_start_date"])
    return str(event.get("start_date")) if event.get("start_date") else None


def _split_name(anchor: str | None, validation_start: str, holdout_start: str) -> str:
    if anchor is None:
        return "train"
    if anchor >= holdout_start:
        return "holdout"
    if anchor >= validation_start:
        return "validation"
    return "train"


def _boundary_exclusion(event: dict[str, Any], split_name: str, validation_start: str, holdout_start: str, embargo_days: int) -> str | None:
    anchor = _date_or_none(_event_anchor_date(event))
    if anchor is None:
        return "missing_event_anchor_date"
    windows = [date for date in (_date_or_none(validation_start), _date_or_none(holdout_start)) if date is not None]
    if any(abs((anchor - boundary).days) <= embargo_days for boundary in windows):
        return f"boundary_purge_embargo_{embargo_days}_days"
    end = _date_or_none(event.get("event_end_date") or event.get("end_date"))
    due = _date_or_none(event.get("outcome_due_date"))
    window_end = max([value for value in (end, due) if value is not None], default=anchor)
    if split_name == "train" and window_end >= _date_or_none(validation_start):
        return "window_crosses_validation_boundary"
    if split_name == "validation" and window_end >= _date_or_none(holdout_start):
        return "window_crosses_holdout_boundary"
    return None


def _unique_resolved_records(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for event in events:
        for record in event.get("_resolved_weekly_records", []) or []:
            if isinstance(record, dict) and record.get("record_id"):
                by_id[str(record["record_id"])] = record
        for case in event.get("cases", []) if isinstance(event.get("cases"), list) else []:
            if isinstance(case, dict) and case.get("date"):
                record_id = f"week:{case['date']}"
                by_id.setdefault(
                    record_id,
                    {
                        "record_id": record_id,
                        "date": case.get("date"),
                        "confirmed_stage": case.get("confirmed_stage") or case.get("domain_confirmed_stage"),
                        "candidate_stage": case.get("candidate_stage") or case.get("domain_candidate_stage"),
                        "max_drawdown_13w": case.get("max_drawdown_13w"),
                    },
                )
    return sorted(by_id.values(), key=lambda row: str(row.get("date") or ""))


def _holdout_primary_coverage(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    denominator = total or 1
    statuses = Counter(str(record.get("primary_coverage_status") or "unavailable") for record in records)
    strict_dates = [str(record.get("date")) for record in records if record.get("primary_strict_available") is True]
    missing_series = Counter(series for record in records for series in record.get("primary_missing_series", []) or [])
    stale_series = Counter(series for record in records for series in record.get("primary_stale_series", []) or [])
    insufficient_series = Counter(series for record in records for series in record.get("primary_history_insufficient_series", []) or [])
    quality_rejected_series = Counter(series for record in records for series in record.get("primary_quality_rejected_series", []) or [])
    return {
        "scope": "holdout_resolved_weekly_records_only",
        "unique_holdout_weekly_case_count": total,
        "strict_count": statuses.get("primary_strict", 0),
        "strict_rate": round(statuses.get("primary_strict", 0) / denominator, 6),
        "partial_count": statuses.get("primary_partial", 0),
        "partial_rate": round(statuses.get("primary_partial", 0) / denominator, 6),
        "fallback_count": statuses.get("fallback", 0),
        "fallback_rate": round(statuses.get("fallback", 0) / denominator, 6),
        "unavailable_count": statuses.get("unavailable", 0),
        "unavailable_rate": round(statuses.get("unavailable", 0) / denominator, 6),
        "missing_series_counts": dict(missing_series),
        "stale_series_counts": dict(stale_series),
        "insufficient_history_series_counts": dict(insufficient_series),
        "quality_rejected_series_counts": dict(quality_rejected_series),
        "event_coverage_count": total,
        "event_coverage_rate": 1.0 if total else 0.0,
        "date_aligned_non_vintage_count": total,
        "date_aligned_non_vintage_rate": 1.0 if total else 0.0,
        "vintage_locked_count": 0,
        "vintage_locked_rate": 0.0,
        "first_strict_holdout_date": min(strict_dates) if strict_dates else None,
        "last_strict_holdout_date": max(strict_dates) if strict_dates else None,
    }


def _split_summary(episodes: list[dict[str, Any]], *, purged_count: int, excluded: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    counts = Counter(str(row.get("primary_classification") or row.get("classification") or "unknown") for row in episodes)
    maturity = _maturity_summary(episodes)
    unique_records = _unique_resolved_records(episodes)
    start_dates = [anchor for row in episodes if (anchor := _event_anchor_date(row)) is not None]
    return {
        "event_count": len(episodes),
        "episode_count": len(episodes),
        "case_count": len(unique_records) if unique_records else sum(int(row.get("case_count", 0) or 0) for row in episodes),
        "purged_overlap_count": purged_count,
        "embargoed_count": purged_count,
        "start_date": min(start_dates, default=None),
        "end_date": max(
            (str(row.get("event_end_date") or row.get("end_date") or _event_anchor_date(row)) for row in episodes), default=None
        ),
        "outcome_due_date": str(episodes[-1].get("outcome_due_date")) if episodes else None,
        "maturity": maturity,
        "performance_denominator": maturity["performance_denominator"],
        "counts": dict(counts),
        "excluded_events": [
            {"event_id": row.get("event_id"), "split": row.get("split"), "exclusion_reason": row.get("exclusion_reason")}
            for row in excluded or []
        ],
        "episodes": episodes,
        "events": episodes,
    }


def _maturity_summary(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(row.get("maturity_status") or row.get("outcome_maturity_status") or "mature") for row in episodes)
    performance_denominator = sum(1 for row in episodes if _episode_performance_evaluable(row))
    return {
        "total_episode_count": len(episodes),
        "mature_episode_count": counts.get("mature", 0),
        "pending_episode_count": counts.get("pending", 0),
        "missing_benchmark_data_episode_count": counts.get("missing_benchmark_data", 0),
        "invalid_alignment_episode_count": counts.get("invalid_alignment", 0),
        "quality_rejected_episode_count": counts.get("quality_rejected", 0),
        "performance_denominator": performance_denominator,
        "performance_denominator_policy": "include_only_mature_quality_valid_exclude_pending_missing_invalid",
    }


def _episode_performance_evaluable(episode: dict[str, Any]) -> bool:
    if "performance_evaluable" not in episode and "outcome_maturity_status" not in episode and "maturity_status" not in episode:
        return True
    maturity = episode.get("maturity_status") or episode.get("outcome_maturity_status")
    return episode.get("performance_evaluable") is True and maturity == "mature"


def _split_boundaries(splits: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {name: {"start_date": split.get("start_date"), "end_date": split.get("end_date")} for name, split in splits.items()}


def _split_status(*, holdout_episode_count: int, minimum_holdout_episodes: int) -> str:
    if holdout_episode_count < minimum_holdout_episodes:
        return "insufficient_holdout_episodes"
    return "ready"


def _evidence_status(*, strict_primary_available: bool) -> str:
    if not strict_primary_available:
        return "blocked_strict_primary_unavailable"
    return "ready"


def _combined_holdout_status(split_status: str, evidence_status: str, performance_status: str) -> str:
    if split_status != "ready":
        return split_status
    if evidence_status != "ready":
        return evidence_status
    if performance_status != "accepted":
        return performance_status
    return "accepted"


def _performance_summary(holdout: dict[str, Any], criteria: HoldoutSplitCriteria, replay_summary: dict[str, Any]) -> dict[str, Any]:
    raw_episodes = holdout.get("episodes")
    episodes: list[Any] = raw_episodes if isinstance(raw_episodes, list) else []
    mature_episodes = [episode for episode in episodes if isinstance(episode, dict) and _episode_performance_evaluable(episode)]
    cases = _unique_resolved_records([episode for episode in episodes if isinstance(episode, dict)])
    mature_cases = _unique_resolved_records(mature_episodes)
    mature_counts = Counter(
        str(episode.get("primary_classification") or episode.get("classification") or "unknown") for episode in mature_episodes
    )
    maturity = _maturity_summary([episode for episode in episodes if isinstance(episode, dict)])
    total = max(1, int(maturity["performance_denominator"] or 0))
    missed = int(mature_counts.get("missed_risk", 0) or 0)
    late = int(mature_counts.get("late_confirmation", 0) or 0)
    protective = int(mature_counts.get("protective", 0) or 0)
    over_warning = int(mature_counts.get("over_warning", 0) or 0)
    insufficient = int(mature_counts.get("insufficient_outcome", 0) or 0)
    invalid_evidence = (
        int(maturity["missing_benchmark_data_episode_count"])
        + int(maturity["invalid_alignment_episode_count"])
        + int(maturity["quality_rejected_episode_count"])
    )
    severe_missed_risk_rate = round(missed / total, 6)
    late_confirmation_rate = round(late / total, 6)
    over_warning_rate = round(over_warning / total, 6)
    metrics: dict[str, Any] = {
        "severe_missed_risk_count": missed,
        "severe_missed_risk_rate": severe_missed_risk_rate,
        "late_confirmation_count": late,
        "late_confirmation_rate": late_confirmation_rate,
        "late_confirmation_median_delay_days": _confirmation_delay_summary(mature_episodes, "late_confirmation").get("median_days"),
        "confirmation_delay": _confirmation_delay_summary(mature_episodes),
        "protective_event_count": protective,
        "protective_episode_count": protective,
        "over_warning_event_count": over_warning,
        "over_warning_episode_count": over_warning,
        "over_warning_rate": over_warning_rate,
        "all_holdout_episode_count": int(holdout.get("episode_count", 0) or 0),
        "mature_episode_count": maturity["mature_episode_count"],
        "pending_episode_count": maturity["pending_episode_count"],
        "quality_rejected_episode_count": maturity["quality_rejected_episode_count"],
        "performance_denominator": maturity["performance_denominator"],
        "performance_denominator_policy": maturity["performance_denominator_policy"],
        "warning_danger_time_in_state": _warning_danger_time_in_state(cases),
        "lead_time_before_material_drawdown_days": _lead_time_summary(mature_episodes).get("median_confirmed_lead_time_days"),
        "lead_time": _lead_time_summary(mature_episodes),
        "max_drawdown_by_confirmed_stage": _max_drawdown_by_confirmed_stage(mature_cases),
        "quiet_period_alert_burden": _quiet_period_alert_burden(mature_episodes),
        "primary_coverage": _holdout_primary_coverage(cases),
        "insufficient_outcome_count": insufficient,
    }
    blockers: list[str] = []
    status = "accepted"
    if invalid_evidence:
        blockers.append("invalid or missing benchmark evidence episodes present in holdout")
        status = "blocked_invalid_evidence"
    if maturity["performance_denominator"] < criteria.minimum_holdout_episodes:
        blockers.append("mature holdout episode count below frozen criterion")
        status = "blocked_insufficient_matured_episodes"
    if severe_missed_risk_rate > criteria.maximum_severe_missed_risk_rate:
        blockers.append("severe missed-risk rate exceeds frozen criterion")
    if late_confirmation_rate > criteria.maximum_late_confirmation_rate:
        blockers.append("late-confirmation rate exceeds frozen criterion")
    if over_warning_rate > criteria.maximum_over_warning_rate:
        blockers.append("over-warning rate exceeds frozen criterion")
    if protective < criteria.minimum_protective_episodes:
        blockers.append("protective episode count below frozen criterion")
    if insufficient:
        blockers.append("insufficient outcome episodes present in holdout")
    if blockers and status == "accepted":
        status = "rejected"
    return {"status": status, "metrics": metrics, "blockers": blockers, "maturity": maturity}


def _confirmation_delay_summary(episodes: list[dict[str, Any]], classification: str | None = None) -> dict[str, Any]:
    selected = [
        episode
        for episode in episodes
        if classification is None or (episode.get("primary_classification") or episode.get("classification")) == classification
    ]
    delays: list[int] = []
    for episode in selected:
        delay = episode.get("confirmation_delay_days", episode.get("confirmation_delay_calendar_days"))
        if delay is not None:
            delays.append(int(delay))
    observation_delays: list[int] = []
    status_counts = Counter("confirmed" if episode.get("first_confirmed_warning_date") else "unconfirmed" for episode in selected)
    return {
        "confirmed_episode_count": status_counts.get("confirmed", 0),
        "unconfirmed_stressed_candidate_count": status_counts.get("not_confirmed_within_horizon", 0),
        "candidate_never_stressed_count": status_counts.get("candidate_never_stressed", 0),
        "median_days": _median(delays),
        "p75_days": _percentile(delays, 0.75),
        "max_days": max(delays) if delays else None,
        "median_observations": _median(observation_delays),
        "status_counts": dict(status_counts),
    }


def _warning_danger_time_in_state(cases: list[dict[str, Any]]) -> dict[str, Any]:
    by_date = {str(case.get("date")): case for case in cases if case.get("date")}
    counts = Counter(
        str(
            case.get("confirmed_stage")
            or case.get("confirmed_stage_key")
            or case.get("confirmed_stage")
            or case.get("confirmed_stage", "normal")
        )
        for case in by_date.values()
    )
    total = len(by_date) or 1
    return {
        "unique_weekly_observations": len(by_date),
        "normal_count": counts.get("normal", 0),
        "warning_count": counts.get("warning", 0),
        "danger_count": counts.get("danger", 0),
        "extreme_count": counts.get("extreme", 0),
        "normal_rate": round(counts.get("normal", 0) / total, 6),
        "warning_rate": round(counts.get("warning", 0) / total, 6),
        "danger_rate": round(counts.get("danger", 0) / total, 6),
        "extreme_rate": round(counts.get("extreme", 0) / total, 6),
        "warning_or_higher_cases": sum(counts.get(stage, 0) for stage in ("warning", "danger", "extreme")),
        "danger_or_higher_cases": sum(counts.get(stage, 0) for stage in ("danger", "extreme")),
        "warning_or_higher_rate": round(sum(counts.get(stage, 0) for stage in ("warning", "danger", "extreme")) / total, 6),
        "danger_or_higher_rate": round(sum(counts.get(stage, 0) for stage in ("danger", "extreme")) / total, 6),
    }


def _lead_time_summary(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    crossing = [
        episode
        for episode in episodes
        if episode.get("first_material_crossing_date") or episode.get("first_material_drawdown_crossing_date")
    ]
    candidate_leads = [
        int(episode["candidate_lead_time_days"]) for episode in crossing if episode.get("candidate_lead_time_days") is not None
    ]
    confirmed_leads = [
        int(episode["confirmed_lead_time_days"]) for episode in crossing if episode.get("confirmed_lead_time_days") is not None
    ]
    return {
        "crossing_episode_count": len(crossing),
        "candidate_lead_time_median_days": _median(candidate_leads),
        "confirmed_lead_time_median_days": _median(confirmed_leads),
        "candidate_lead_time_min_days": min(candidate_leads) if candidate_leads else None,
        "confirmed_lead_time_min_days": min(confirmed_leads) if confirmed_leads else None,
        "not_confirmed_crossing_count": sum(1 for episode in crossing if episode.get("confirmed_lead_time_status") == "not_confirmed"),
    }


def _max_drawdown_by_confirmed_stage(cases: list[dict[str, Any]]) -> dict[str, float | None]:
    grouped: dict[str, list[float]] = {}
    for case in cases:
        stage = str(case.get("confirmed_stage") or case.get("domain_confirmed_stage") or "normal")
        value = case.get("max_drawdown_13w")
        if value is not None:
            grouped.setdefault(stage, []).append(float(value))
    return {stage: min(values) if values else None for stage, values in grouped.items()}


def _quiet_period_alert_burden(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    quiet_episodes = [
        episode for episode in episodes if (episode.get("primary_classification") or episode.get("classification")) == "over_warning"
    ]
    denominator = len(quiet_episodes) or 1
    warning_or_higher = [
        episode
        for episode in quiet_episodes
        if any(
            str(record.get("confirmed_stage") or "normal") in {"warning", "danger", "extreme"}
            for record in episode.get("_resolved_weekly_records", []) or []
        )
        or any(str(stage) in {"warning", "danger", "extreme"} for stage in episode.get("confirmed_stages", []) or [])
    ]
    danger_or_higher = [
        episode
        for episode in quiet_episodes
        if any(
            str(record.get("confirmed_stage") or "normal") in {"danger", "extreme"}
            for record in episode.get("_resolved_weekly_records", []) or []
        )
        or any(str(stage) in {"danger", "extreme"} for stage in episode.get("confirmed_stages", []) or [])
    ]
    return {
        "quiet_definition": "mature and no material 4w drawdown, 13w drawdown, or 13w loss",
        "mature_quiet_episode_count": len(quiet_episodes),
        "quiet_warning_or_higher_episode_count": len(warning_or_higher),
        "quiet_danger_or_higher_episode_count": len(danger_or_higher),
        "quiet_alert_episode_rate": round(len(warning_or_higher) / denominator, 6),
        "quiet_danger_episode_rate": round(len(danger_or_higher) / denominator, 6),
        "time_in_warning_during_quiet": _quiet_time_in_state(quiet_episodes, {"warning", "danger", "extreme"}),
        "time_in_danger_during_quiet": _quiet_time_in_state(quiet_episodes, {"danger", "extreme"}),
    }


def _quiet_time_in_state(episodes: list[dict[str, Any]], stages: set[str]) -> int:
    dates: set[str] = set()
    for episode in episodes:
        for case in episode.get("cases", []) if isinstance(episode.get("cases"), list) else []:
            if isinstance(case, dict) and str(case.get("confirmed_stage")) in stages and case.get("date"):
                dates.add(str(case["date"]))
    return len(dates)


def _date_or_none(value: Any) -> Any:
    from datetime import date

    import pandas as pd

    if value is None:
        return None
    try:
        parsed = pd.Timestamp(value)
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    result = parsed.date()
    return result if isinstance(result, date) else None


def _median(values: list[int]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2


def _percentile(values: list[int], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * percentile))))
    return float(ordered[index])


def _cadence_status(replay_payload: dict[str, Any], replay_summary: dict[str, Any]) -> str:
    raw_reconstruction = replay_payload.get("reconstruction")
    reconstruction: dict[str, Any] = raw_reconstruction if isinstance(raw_reconstruction, dict) else {}
    raw_cadence = reconstruction.get("cadence")
    cadence: dict[str, Any] = raw_cadence if isinstance(raw_cadence, dict) else {}
    if cadence.get("engine_evaluation_cadence") != "canonical_weekly":
        return "engine_evaluation_cadence_not_weekly"
    if cadence.get("persistence_expected_cadence") != "canonical_weekly":
        return "persistence_expected_cadence_not_weekly"
    if cadence.get("stride_semantics") != "case_sampling_only_not_persistence_update":
        return "case_sampling_stride_may_skip_persistence"
    gap_rate = float(replay_summary.get("persistence_gap_reset_rate", 0.0) or 0.0)
    if gap_rate > 0.05:
        return "persistence_gap_reset_rate_too_high"
    return "valid"


def _holdout_reason(status: str) -> str:
    return {
        "blocked_strict_primary_unavailable": "strict primary official-series replay is unavailable, so holdout is not promotion evidence",
        "insufficient_holdout_episodes": "holdout episode count is below the frozen minimum",
        "blocked_insufficient_matured_episodes": "mature holdout episode count is below the frozen minimum",
        "blocked_invalid_evidence": "holdout contains invalid or missing benchmark evidence",
        "rejected": "frozen performance acceptance criteria did not pass",
        "blocked_invalid_cadence": "replay cadence is invalid for promotion evidence",
        "accepted": "split, evidence, and frozen performance criteria pass, but manual approval is still required",
    }.get(status, status)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run diagnostic risk_engine_v2 frozen holdout validation.")
    parser.add_argument("--replay-json", default="project/reports/risk_engine_v2_reconstructed_replay.json")
    parser.add_argument("--review-json", default="project/reports/risk_engine_v2_replay_review.json")
    parser.add_argument("--reports-dir", default="project/reports")
    args = parser.parse_args()
    print(
        json.dumps(
            run_risk_engine_v2_holdout_validation(args.replay_json, args.review_json, args.reports_dir),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
