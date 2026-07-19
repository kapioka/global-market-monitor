from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from project.risk_engine_v2_contract import attach_shadow_diagnostic_contract
from project.risk_engine_v2_market_events import build_market_event_review
from project.risk_engine_v2_promotion_gate import evaluate_risk_engine_v2_promotion_gate

STRESSED_STAGES = {"warning", "danger", "extreme"}
REVIEW_CLASSES = (
    "protective",
    "over_warning",
    "ambiguous",
    "missed_risk",
    "late_confirmation",
    "insufficient_outcome",
)


@dataclass(frozen=True)
class ReviewThresholds:
    material_loss_13w: float = -0.05
    material_drawdown_13w: float = -0.08
    material_drawdown_4w: float = -0.08
    benign_drawdown_13w: float = -0.05
    over_warning_return_13w: float = 0.0
    episode_horizon_days: int = 91
    min_sample_for_ci: int = 30

    @classmethod
    def from_settings(cls, settings: dict[str, Any] | None = None) -> ReviewThresholds:
        payload = settings or {}
        return cls(
            material_loss_13w=float(payload.get("material_loss_13w", cls.material_loss_13w)),
            material_drawdown_13w=float(payload.get("material_drawdown_13w", cls.material_drawdown_13w)),
            material_drawdown_4w=float(payload.get("material_drawdown_4w", cls.material_drawdown_4w)),
            benign_drawdown_13w=float(payload.get("benign_drawdown_13w", cls.benign_drawdown_13w)),
            over_warning_return_13w=float(payload.get("over_warning_return_13w", cls.over_warning_return_13w)),
            episode_horizon_days=int(payload.get("episode_horizon_days", cls.episode_horizon_days)),
            min_sample_for_ci=int(payload.get("min_sample_for_ci", cls.min_sample_for_ci)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "material_loss_13w": self.material_loss_13w,
            "material_drawdown_13w": self.material_drawdown_13w,
            "material_drawdown_4w": self.material_drawdown_4w,
            "benign_drawdown_13w": self.benign_drawdown_13w,
            "over_warning_return_13w": self.over_warning_return_13w,
            "episode_horizon_days": self.episode_horizon_days,
            "min_sample_for_ci": self.min_sample_for_ci,
        }


def build_risk_engine_v2_replay_review(
    payload: dict[str, Any],
    *,
    thresholds: dict[str, Any] | ReviewThresholds | None = None,
) -> dict[str, Any]:
    review_thresholds = thresholds if isinstance(thresholds, ReviewThresholds) else ReviewThresholds.from_settings(thresholds)
    outcome_observed_through = _outcome_observed_through(payload)
    case_evidence = [_case_evidence(case, review_thresholds, outcome_observed_through) for case in payload.get("cases", [])]
    episodes = _build_episodes(case_evidence, review_thresholds)
    counts = {name: 0 for name in REVIEW_CLASSES}
    for episode in episodes:
        counts[str(episode["classification"])] += 1
    usable_cases = sum(1 for case in case_evidence if case["outcome_status"] == "ok")
    review = {
        "status": "ok" if case_evidence else "missing_cases",
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "source_replay_type": payload.get("replay_type"),
        "review_level": "episode",
        "usable_cases": usable_cases,
        "case_count": len(case_evidence),
        "episode_count": len(episodes),
        "episode_maturity": _episode_maturity_summary(episodes),
        "criteria": {
            "protective": "confirmed warning-or-higher with material 13w loss or material drawdown",
            "over_warning": "confirmed warning-or-higher with complete benign 13w outcome and no material drawdown",
            "ambiguous": "stressed or relevant case with complete outcome but neither protective nor over-warning",
            "missed_risk": "confirmed normal without candidate stress, followed by material adverse outcome",
            "late_confirmation": "candidate warning-or-higher but confirmed normal, followed by material adverse outcome",
            "insufficient_outcome": "missing or incomplete 13w return/drawdown outcome",
        },
        "thresholds": review_thresholds.to_dict(),
        "counts": counts,
        "confidence": _confidence_summary(counts, len(episodes), review_thresholds.min_sample_for_ci),
        "episodes": episodes,
        "case_evidence": case_evidence,
        "decision": {
            "promotion_allowed": False,
            "reason": "episode-level diagnostic review only; calibration acceptance and holdout validation are not met",
        },
    }
    event_review = build_market_event_review(payload, review)
    event_review.update(
        {
            "usable_cases": usable_cases,
            "case_count": len(case_evidence),
            "criteria": {
                "event_ownership": "one market drawdown event owns its full weekly timeline once",
                "material_drawdown": "primary benchmark drawdown crosses the versioned event policy threshold",
                "alert_only": "confirmed warning-or-higher weekly timeline segment not owned by a material drawdown event",
                "protective": "confirmed warning-or-higher before or at material drawdown crossing",
                "late_confirmation": "candidate warning-or-higher before crossing, confirmed only after crossing",
                "missed_risk": "no candidate or confirmed stress before material drawdown crossing",
                "over_warning": "mature alert-only event with benign forward outcome",
                "insufficient_outcome": "event horizon is not fully observable",
            },
            "legacy_episode_review": {
                "review_level": review["review_level"],
                "episode_count": review["episode_count"],
                "episode_maturity": review["episode_maturity"],
                "thresholds": review["thresholds"],
                "counts": review["counts"],
                "confidence": review["confidence"],
                "episodes": review["episodes"],
                "case_evidence": review["case_evidence"],
            },
        }
    )
    promotion_gate = evaluate_risk_engine_v2_promotion_gate(payload, event_review)
    event_review["promotion_gate"] = promotion_gate
    event_review["decision"] = {
        "promotion_allowed": False,
        "reason": promotion_gate["reason"],
    }
    return attach_shadow_diagnostic_contract(event_review, artifact_type="review")


def render_risk_engine_v2_replay_review_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# risk_engine_v2 replay review",
        "",
        "This review is diagnostic only. It does not change final_action, buy_readiness_score, or thresholds.",
        "",
        "## Summary",
        "",
        f"- status: {review.get('status', '-')}",
        f"- source_replay_type: {review.get('source_replay_type', '-')}",
        f"- review_level: {review.get('review_level', '-')}",
        f"- usable_cases: {review.get('usable_cases', 0)}",
        f"- case_count: {review.get('case_count', 0)}",
        f"- episode_count: {review.get('episode_count', 0)}",
        f"- policy_status: {review.get('policy_status', '-')}",
        f"- affects_final_action: {review.get('affects_final_action', False)}",
    ]
    counts = review.get("counts") or {}
    for key in REVIEW_CLASSES:
        lines.append(f"- {key}: {counts.get(key, 0)}")
    lines.extend(["", "## Thresholds", ""])
    for key, value in (review.get("thresholds") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Confidence", ""])
    for key, value in (review.get("confidence") or {}).items():
        lines.append(f"- {key}: {value}")
    gate = review.get("promotion_gate") or {}
    lines.extend(["", "## Promotion Gate", ""])
    lines.append(f"- status: {gate.get('status', '-')}")
    lines.append(f"- promotion_allowed: {gate.get('promotion_allowed', False)}")
    lines.append(f"- reason: {gate.get('reason', '-')}")
    for blocker in gate.get("blockers", []) or []:
        lines.append(f"- blocker: {blocker}")
    for warning in gate.get("warnings", []) or []:
        lines.append(f"- warning: {warning}")
    lines.extend(["", "## Criteria", ""])
    for key, value in (review.get("criteria") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Events", ""])
    for row in review.get("episodes", []):
        lines.append(
            "- {episode_id}: {event_type} {classification} {start}..{end} records={count}".format(
                episode_id=row.get("event_id", row.get("episode_id", "-")),
                event_type=row.get("event_type", "-"),
                classification=row.get("classification", "-"),
                start=row.get("start_date", "-"),
                end=row.get("end_date", "-"),
                count=row.get("case_count", len(row.get("weekly_timeline_record_ids", []) or [])),
            )
        )
    if review.get("legacy_episode_review"):
        legacy = review["legacy_episode_review"]
        lines.extend(["", "## Legacy Episode Mapping", ""])
        lines.append(f"- legacy_episode_count: {legacy.get('episode_count', 0)}")
        lines.append(f"- unmapped_old_episode_count: {review.get('unmapped_old_episode_count', 0)}")
    decision = review.get("decision") or {}
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- promotion_allowed: {decision.get('promotion_allowed', False)}",
            f"- reason: {decision.get('reason', '-')}",
        ]
    )
    return "\n".join(lines) + "\n"


def run_risk_engine_v2_replay_review(
    replay_json: str | Path = "project/reports/risk_engine_v2_reconstructed_replay.json",
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    replay_path = Path(replay_json)
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    if not replay_path.exists():
        return {"status": "missing_replay", "replay_json": str(replay_path)}
    payload = json.loads(replay_path.read_text(encoding="utf-8"))
    review = build_risk_engine_v2_replay_review(payload)
    json_path = reports_path / "risk_engine_v2_replay_review.json"
    markdown_path = reports_path / "risk_engine_v2_replay_review.md"
    json_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_risk_engine_v2_replay_review_markdown(review), encoding="utf-8")
    return {
        "status": review.get("status"),
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "usable_cases": review.get("usable_cases", 0),
        "episode_count": review.get("episode_count", 0),
        "counts": review.get("counts", {}),
        "policy_status": review.get("policy_status"),
        "affects_final_action": review.get("affects_final_action"),
        "decision": review.get("decision", {}),
    }


def _case_evidence(case: dict[str, Any], thresholds: ReviewThresholds, outcome_observed_through: str | None) -> dict[str, Any]:
    outcome = case.get("outcome") or {}
    date = str(case.get("date") or "")
    confirmed = str(case.get("domain_confirmed_stage") or "normal")
    candidate = str(case.get("domain_candidate_stage") or "normal")
    return_13w = _forward(case, "13w")
    max_drawdown_13w = _drawdown(case, "13w")
    max_drawdown_4w = _drawdown(case, "4w")
    drawdown_path_13w = _drawdown_path(case, "13w")
    crossing_date = _first_drawdown_crossing_date(drawdown_path_13w, thresholds.material_drawdown_13w)
    complete = outcome.get("status") == "ok" and return_13w is not None and max_drawdown_13w is not None
    material_adverse = False
    if complete and return_13w is not None and max_drawdown_13w is not None:
        material_adverse = (
            return_13w <= thresholds.material_loss_13w
            or max_drawdown_13w <= thresholds.material_drawdown_13w
            or (max_drawdown_4w is not None and max_drawdown_4w <= thresholds.material_drawdown_4w)
        )
    classification = _classify_case(
        candidate=candidate,
        confirmed=confirmed,
        complete=complete,
        material_adverse=bool(material_adverse),
        return_13w=return_13w,
        max_drawdown_13w=max_drawdown_13w,
        thresholds=thresholds,
    )
    outcome_due_date = _episode_end_date(date, thresholds.episode_horizon_days)
    maturity_status, pending_reason = _outcome_maturity_status(
        date=date,
        outcome_due_date=outcome_due_date,
        outcome_status=outcome.get("status"),
        complete=complete,
        outcome_observed_through=outcome_observed_through,
    )
    return {
        "date": date,
        "episode_end_date": outcome_due_date,
        "classification": classification,
        "candidate_stage": candidate,
        "confirmed_stage": confirmed,
        "legacy_stage": case.get("legacy_stage"),
        "oil_status": case.get("oil_status"),
        "outcome_status": outcome.get("status"),
        "complete_13w_outcome": complete,
        "outcome_anchor_date": date,
        "outcome_horizon": "13w",
        "outcome_due_date": outcome_due_date,
        "outcome_observed_through": outcome_observed_through,
        "outcome_maturity_status": maturity_status,
        "performance_evaluable": maturity_status == "mature",
        "pending_reason": pending_reason,
        "material_adverse_outcome": bool(material_adverse),
        "material_drawdown_threshold": thresholds.material_drawdown_13w,
        "first_material_drawdown_crossing_date": crossing_date,
        "crossing_status": "crossed" if crossing_date else "not_applicable",
        "return_4w": _round_or_none(_forward(case, "4w")),
        "return_13w": _round_or_none(return_13w),
        "return_26w": _round_or_none(_forward(case, "26w")),
        "max_drawdown_4w": _round_or_none(max_drawdown_4w),
        "max_drawdown_13w": _round_or_none(max_drawdown_13w),
        "max_drawdown_26w": _round_or_none(_drawdown(case, "26w")),
        "drawdown_path_13w": drawdown_path_13w,
    }


def _classify_case(
    *,
    candidate: str,
    confirmed: str,
    complete: bool,
    material_adverse: bool,
    return_13w: float | None,
    max_drawdown_13w: float | None,
    thresholds: ReviewThresholds,
) -> str:
    if not complete:
        return "insufficient_outcome"
    candidate_stressed = candidate in STRESSED_STAGES
    confirmed_stressed = confirmed in STRESSED_STAGES
    if confirmed_stressed and material_adverse:
        return "protective"
    if confirmed_stressed and return_13w is not None and max_drawdown_13w is not None:
        if return_13w >= thresholds.over_warning_return_13w and max_drawdown_13w > thresholds.benign_drawdown_13w:
            return "over_warning"
        return "ambiguous"
    if candidate_stressed and not confirmed_stressed and material_adverse:
        return "late_confirmation"
    if not candidate_stressed and not confirmed_stressed and material_adverse:
        return "missed_risk"
    return "ambiguous"


def _build_episodes(case_evidence: list[dict[str, Any]], thresholds: ReviewThresholds) -> list[dict[str, Any]]:
    sorted_cases = sorted(case_evidence, key=lambda row: row["date"])
    episodes: list[dict[str, Any]] = []
    for case in sorted_cases:
        classification = str(case["classification"])
        start = case["date"]
        end = case["episode_end_date"] or start
        if episodes and episodes[-1]["classification"] == classification and start <= str(episodes[-1]["outcome_due_date"]):
            _append_case_to_episode(episodes[-1], case, end)
            continue
        episode = {
            "episode_id": f"episode-{len(episodes) + 1:04d}",
            "classification": classification,
            "start_date": start,
            "end_date": start,
            "signal_start_date": start,
            "signal_end_date": start,
            "outcome_anchor_date": start,
            "outcome_horizon": "13w",
            "outcome_due_date": end,
            "outcome_observed_through": case.get("outcome_observed_through"),
            "outcome_maturity_status": case.get("outcome_maturity_status"),
            "performance_evaluable": bool(case.get("performance_evaluable")),
            "pending_reason": case.get("pending_reason"),
            "case_count": 1,
            "case_dates": [start],
            "candidate_stages": [case["candidate_stage"]],
            "confirmed_stages": [case["confirmed_stage"]],
            "worst_return_13w": case.get("return_13w"),
            "worst_max_drawdown_4w": case.get("max_drawdown_4w"),
            "worst_max_drawdown_13w": case.get("max_drawdown_13w"),
            "cases": [case],
        }
        episodes.append(episode)
    for episode in episodes:
        _finalize_episode_metrics(episode, thresholds)
    return episodes


def _append_case_to_episode(episode: dict[str, Any], case: dict[str, Any], end: str) -> None:
    episode["end_date"] = max(str(episode["end_date"]), str(case["date"]))
    episode["signal_end_date"] = max(str(episode["signal_end_date"]), str(case["date"]))
    episode["outcome_due_date"] = max(str(episode["outcome_due_date"]), end)
    episode["outcome_observed_through"] = _max_optional_date(episode.get("outcome_observed_through"), case.get("outcome_observed_through"))
    episode["outcome_maturity_status"], episode["pending_reason"] = _combine_episode_maturity(
        [*(row.get("outcome_maturity_status") for row in episode.get("cases", [])), case.get("outcome_maturity_status")]
    )
    episode["performance_evaluable"] = episode["outcome_maturity_status"] == "mature"
    episode["case_count"] = int(episode["case_count"]) + 1
    episode["case_dates"].append(case["date"])
    episode["candidate_stages"].append(case["candidate_stage"])
    episode["confirmed_stages"].append(case["confirmed_stage"])
    episode["worst_return_13w"] = _min_optional(episode.get("worst_return_13w"), case.get("return_13w"))
    episode["worst_max_drawdown_4w"] = _min_optional(episode.get("worst_max_drawdown_4w"), case.get("max_drawdown_4w"))
    episode["worst_max_drawdown_13w"] = _min_optional(episode.get("worst_max_drawdown_13w"), case.get("max_drawdown_13w"))
    episode["cases"].append(case)


def _finalize_episode_metrics(episode: dict[str, Any], thresholds: ReviewThresholds) -> None:
    cases = sorted((case for case in episode.get("cases", []) if isinstance(case, dict)), key=lambda row: str(row.get("date") or ""))
    candidate_dates = [str(case["date"]) for case in cases if str(case.get("candidate_stage")) in STRESSED_STAGES]
    first_candidate = candidate_dates[0] if candidate_dates else None
    confirmed_dates = [
        str(case["date"])
        for case in cases
        if str(case.get("confirmed_stage")) in STRESSED_STAGES and (first_candidate is None or str(case.get("date")) >= first_candidate)
    ]
    first_confirmed = confirmed_dates[0] if confirmed_dates else None
    crossing_dates = [
        str(case["first_material_drawdown_crossing_date"]) for case in cases if case.get("first_material_drawdown_crossing_date")
    ]
    first_crossing = min(crossing_dates) if crossing_dates else None
    episode["first_candidate_stress_date"] = first_candidate
    episode["first_confirmed_stress_date"] = first_confirmed
    episode["confirmation_status"] = _confirmation_status(first_candidate, first_confirmed, cases)
    episode["confirmation_delay_calendar_days"] = (
        _date_diff_days(first_candidate, first_confirmed) if first_candidate and first_confirmed else None
    )
    episode["confirmation_delay_observations"] = _observation_delay(cases, first_candidate, first_confirmed)
    episode["material_drawdown_threshold"] = thresholds.material_drawdown_13w
    episode["first_material_drawdown_crossing_date"] = first_crossing
    episode["crossing_status"] = "crossed" if first_crossing else "not_applicable"
    episode["candidate_lead_time_days"] = _date_diff_days(first_candidate, first_crossing) if first_candidate and first_crossing else None
    if first_confirmed and first_crossing:
        episode["confirmed_lead_time_days"] = _date_diff_days(first_confirmed, first_crossing)
    else:
        episode["confirmed_lead_time_days"] = None
    episode["confirmed_lead_time_status"] = (
        "not_applicable" if not first_crossing else ("not_confirmed" if not first_confirmed else "calculated")
    )
    worst_return = episode.get("worst_return_13w")
    worst_dd4 = _min_many(case.get("max_drawdown_4w") for case in cases)
    worst_dd13 = episode.get("worst_max_drawdown_13w")
    episode["worst_max_drawdown_4w"] = worst_dd4
    episode["quiet_outcome"] = (
        episode.get("outcome_maturity_status") == "mature"
        and worst_return is not None
        and worst_dd4 is not None
        and worst_dd13 is not None
        and float(worst_return) > thresholds.material_loss_13w
        and float(worst_dd4) > thresholds.material_drawdown_4w
        and float(worst_dd13) > thresholds.material_drawdown_13w
    )
    episode["quiet_definition"] = "mature and no material 4w drawdown, 13w drawdown, or 13w loss"


def _episode_maturity_summary(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(episode.get("outcome_maturity_status") or "mature") for episode in episodes)
    performance_denominator = sum(1 for episode in episodes if _episode_performance_evaluable(episode))
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
    if "performance_evaluable" not in episode and "outcome_maturity_status" not in episode:
        return True
    return episode.get("performance_evaluable") is True and episode.get("outcome_maturity_status") == "mature"


def _confidence_summary(counts: dict[str, int], total: int, min_sample: int) -> dict[str, Any]:
    if total < min_sample:
        return {
            "sample_size_note": f"insufficient sample size for stable confidence intervals: {total} < {min_sample}",
            "intervals": {},
        }
    return {
        "sample_size_note": "wilson_95pct_intervals",
        "intervals": {key: _wilson_interval(value, total) for key, value in counts.items()},
    }


def _wilson_interval(successes: int, total: int) -> dict[str, float]:
    if total <= 0:
        return {"lower": 0.0, "upper": 0.0}
    z = 1.96
    p = successes / total
    denom = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denom
    margin = z * math.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denom
    return {"lower": round(max(0.0, center - margin), 6), "upper": round(min(1.0, center + margin), 6)}


def _episode_end_date(date_text: str, horizon_days: int) -> str | None:
    if not date_text:
        return None
    return (pd_timestamp(date_text) + pd_timedelta(days=horizon_days)).date().isoformat()


def _outcome_observed_through(payload: dict[str, Any]) -> str | None:
    reconstruction = payload.get("reconstruction")
    if isinstance(reconstruction, dict) and reconstruction.get("end_date"):
        return str(reconstruction["end_date"])
    case_dates = [str(case.get("date")) for case in payload.get("cases", []) if isinstance(case, dict) and case.get("date")]
    return max(case_dates) if case_dates else None


def _outcome_maturity_status(
    *,
    date: str,
    outcome_due_date: str | None,
    outcome_status: Any,
    complete: bool,
    outcome_observed_through: str | None,
) -> tuple[str, str | None]:
    if not date or outcome_due_date is None:
        return "invalid_alignment", "missing case date or outcome due date"
    due = _date_or_none(outcome_due_date)
    observed = _date_or_none(outcome_observed_through)
    if due is None or observed is None:
        return "invalid_alignment", "missing outcome observed-through date"
    if complete:
        return "mature", None
    if observed < due:
        return "pending", f"outcome horizon due {outcome_due_date} but observed through {outcome_observed_through}"
    if outcome_status in {"quality_rejected", "invalid_quality"}:
        return "quality_rejected", str(outcome_status)
    return "missing_benchmark_data", str(outcome_status or "missing_outcome")


def _combine_episode_maturity(statuses: list[Any]) -> tuple[str, str | None]:
    normalized = [str(status or "mature") for status in statuses]
    for status in ("invalid_alignment", "quality_rejected", "missing_benchmark_data", "pending"):
        if status in normalized:
            return status, f"one or more episode cases are {status}"
    return "mature", None


def _max_optional_date(left: Any, right: Any) -> str | None:
    values = [str(value) for value in (left, right) if value]
    return max(values) if values else None


def _confirmation_status(first_candidate: str | None, first_confirmed: str | None, cases: list[dict[str, Any]]) -> str:
    if not cases:
        return "insufficient_timeline"
    if not first_candidate:
        return "candidate_never_stressed"
    if first_confirmed:
        return "confirmed"
    return "not_confirmed_within_horizon"


def _date_diff_days(start: str | None, end: str | None) -> int | None:
    start_date = _date_or_none(start)
    end_date = _date_or_none(end)
    if start_date is None or end_date is None:
        return None
    return int((end_date - start_date).days)


def _observation_delay(cases: list[dict[str, Any]], start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    dates = [str(case.get("date")) for case in cases if case.get("date")]
    try:
        return dates.index(end) - dates.index(start)
    except ValueError:
        return None


def _first_drawdown_crossing_date(path: list[dict[str, Any]], threshold: float) -> str | None:
    for point in path:
        value = point.get("drawdown_from_anchor")
        if value is not None and float(value) <= threshold:
            return str(point.get("date"))
    return None


def _date_or_none(value: Any) -> Any:
    import pandas as pd

    if value is None:
        return None
    try:
        parsed = pd.Timestamp(value)
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    return parsed.date()


def pd_timestamp(value: str) -> Any:
    import pandas as pd

    return pd.Timestamp(value)


def pd_timedelta(*, days: int) -> Any:
    import pandas as pd

    return pd.Timedelta(days=days)


def _min_optional(left: Any, right: Any) -> Any:
    values = [value for value in (left, right) if value is not None]
    return min(values) if values else None


def _min_many(values: Any) -> Any:
    present = [value for value in values if value is not None]
    return min(present) if present else None


def _forward(case: dict[str, Any], horizon: str) -> float | None:
    value = ((case.get("outcome") or {}).get("forward_returns") or {}).get(horizon)
    return float(value) if value is not None else None


def _drawdown(case: dict[str, Any], horizon: str) -> float | None:
    value = ((case.get("outcome") or {}).get("max_drawdowns") or {}).get(horizon)
    return float(value) if value is not None else None


def _drawdown_path(case: dict[str, Any], horizon: str) -> list[dict[str, Any]]:
    raw_path = ((case.get("outcome") or {}).get("drawdown_paths") or {}).get(horizon)
    return list(raw_path) if isinstance(raw_path, list) else []


def _round_or_none(value: float | None) -> float | None:
    return round(value, 6) if value is not None else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Review reconstructed risk_engine_v2 false/late signal episodes.")
    parser.add_argument("--replay-json", default="project/reports/risk_engine_v2_reconstructed_replay.json")
    parser.add_argument("--reports-dir", default="project/reports")
    args = parser.parse_args()
    print(json.dumps(run_risk_engine_v2_replay_review(args.replay_json, args.reports_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
