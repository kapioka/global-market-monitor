from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from project.config_loader import load_config
from project.risk_line_recalibration_pipeline import write_risk_line_recalibration_outputs
from project.risk_line_threshold_drift_report import load_risk_line_threshold_drift_snapshot, write_risk_line_threshold_drift_report
from project.risk_line_threshold_store import ACTIVE_THRESHOLDS_PATH, load_threshold_payload

RECALIBRATION_SUMMARY_JSON = "risk_line_recalibration_summary.json"
RECALIBRATION_DIFF_JSON = "risk_line_threshold_diff.json"


def load_risk_line_review_status(reports_dir: str | Path, active_threshold_payload: dict[str, Any], recalibration_policy: dict[str, Any] | None = None, as_of: datetime | None = None) -> dict[str, Any]:
    reports_path = Path(reports_dir)
    drift_snapshot = load_risk_line_threshold_drift_snapshot(reports_path)
    recal_summary = _load_json_if_exists(reports_path / RECALIBRATION_SUMMARY_JSON)
    recal_diff = _load_json_if_exists(reports_path / RECALIBRATION_DIFF_JSON)
    return build_risk_line_review_status(
        active_threshold_payload=active_threshold_payload,
        drift_snapshot=drift_snapshot,
        recalibration_summary=recal_summary,
        recalibration_diff=recal_diff,
        recalibration_policy=recalibration_policy,
        as_of=as_of,
    )


def build_risk_line_review_status(active_threshold_payload: dict[str, Any], drift_snapshot: dict[str, Any] | None = None, recalibration_summary: dict[str, Any] | None = None, recalibration_diff: dict[str, Any] | None = None, recalibration_policy: dict[str, Any] | None = None, as_of: datetime | None = None) -> dict[str, Any]:
    policy = {"cadence_days": 90, "warning_days": 14, "auto_generate_proposal": True, "generate_on_drift_review": True, **(recalibration_policy or {})}
    now = as_of or datetime.now().astimezone()
    threshold_set = active_threshold_payload.get("threshold_set", {})
    active_generated_at = _parse_iso(threshold_set.get("generated_at"))
    days_since_active = None
    if active_generated_at is not None:
        days_since_active = max((now.date() - active_generated_at.date()).days, 0)

    cadence_days = int(policy.get("cadence_days", 90) or 90)
    warning_days = int(policy.get("warning_days", 14) or 14)
    due_for_recalibration = days_since_active is not None and days_since_active >= cadence_days
    near_due = days_since_active is not None and days_since_active >= max(cadence_days - warning_days, 0)

    drift_summary = (drift_snapshot or {}).get("summary") or {}
    drift_review_count = int(drift_summary.get("review_count", 0) or 0)
    drift_watch_count = int(drift_summary.get("watch_count", 0) or 0)
    drift_review_targets = list(drift_summary.get("review_targets", []) or [])

    diff_summary = (recalibration_diff or {}).get("summary") or {}
    proposal_change_count = int(diff_summary.get("changed", 0) or 0) + int(diff_summary.get("added", 0) or 0) + int(diff_summary.get("removed", 0) or 0)

    review_recommended = bool(due_for_recalibration or drift_review_count > 0 or proposal_change_count > 0)
    status = "normal"
    if review_recommended:
        status = "review"
    elif near_due or drift_watch_count > 0:
        status = "watch"

    reasons: list[str] = []
    if due_for_recalibration:
        reasons.append(f"recalibration_due:{days_since_active}d")
    elif near_due and days_since_active is not None:
        reasons.append(f"recalibration_near_due:{days_since_active}d")
    if drift_review_count > 0:
        reasons.append("drift_review_targets:" + ",".join(drift_review_targets))
    elif drift_watch_count > 0:
        reasons.append(f"drift_watch_count:{drift_watch_count}")
    if proposal_change_count > 0:
        reasons.append(f"proposal_changes:{proposal_change_count}")

    return {
        "status": status,
        "review_recommended": review_recommended,
        "days_since_active": days_since_active,
        "cadence_days": cadence_days,
        "warning_days": warning_days,
        "due_for_recalibration": bool(due_for_recalibration),
        "near_due": bool(near_due),
        "drift_review_count": drift_review_count,
        "drift_watch_count": drift_watch_count,
        "drift_review_targets": drift_review_targets,
        "proposal_change_count": proposal_change_count,
        "active_version": threshold_set.get("version"),
        "proposed_version": (recalibration_summary or {}).get("proposed_version"),
        "last_recalibration_summary_at": (recalibration_summary or {}).get("generated_at"),
        "reasons": reasons,
    }


def run_periodic_risk_line_maintenance(config_path: str | Path, sample_only: bool = False, as_of: datetime | None = None) -> dict[str, Any]:
    return run_periodic_risk_line_maintenance_with_progress(config_path, sample_only=sample_only, as_of=as_of)


def run_periodic_risk_line_maintenance_with_progress(
    config_path: str | Path,
    sample_only: bool = False,
    as_of: datetime | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    policy = config.get("risk_line_recalibration", {})
    active_payload = load_threshold_payload(ACTIVE_THRESHOLDS_PATH)
    reports_dir = config.get("paths", {}).get("reports_dir")
    started = time.perf_counter()
    events: list[dict[str, Any]] = []

    def emit(stage: str, message: str, **extra: Any) -> None:
        event = {
            "stage": stage,
            "message": message,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            **extra,
        }
        events.append(event)
        if progress_callback is not None:
            progress_callback(event)

    emit("0/4", "threshold maintenance starting")
    if not reports_dir:
        status = build_risk_line_review_status(active_payload, recalibration_policy=policy, as_of=as_of)
        emit("4/4", "threshold maintenance completed", proposal_generated=False)
        status["maintenance"] = {
            "status": "completed",
            "events": events,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "proposal_generated_this_run": False,
        }
        return status

    if bool(policy.get("refresh_drift_on_run", True)):
        emit("1/4", "refreshing threshold drift report")
        write_risk_line_threshold_drift_report(config_path, sample_only=sample_only)
    else:
        emit("1/4", "skipping threshold drift refresh")

    emit("2/4", "loading threshold review status")
    status = load_risk_line_review_status(reports_dir, active_payload, policy, as_of=as_of)
    should_generate = bool(policy.get("auto_generate_proposal", True)) and bool(status.get("due_for_recalibration"))
    if bool(policy.get("generate_on_drift_review", True)) and int(status.get("drift_review_count", 0) or 0) > 0:
        should_generate = True
    if should_generate:
        emit("3/4", "generating recalibration proposal")
        write_proposed = bool(policy.get("write_proposed_thresholds", False)) and not sample_only
        outputs = write_risk_line_recalibration_outputs(config_path, sample_only=sample_only, write_proposed=write_proposed)
        status = load_risk_line_review_status(reports_dir, active_payload, policy, as_of=as_of)
        status["proposal_generated_this_run"] = True
        status["proposed_thresholds_written"] = bool(outputs.get("proposed_json"))
        status["proposed_thresholds_snapshot"] = str(outputs.get("proposed_snapshot_json")) if outputs.get("proposed_snapshot_json") else None
    else:
        emit("3/4", "proposal generation not required")
        status["proposal_generated_this_run"] = False
        status["proposed_thresholds_written"] = False
    emit("4/4", "threshold maintenance completed", proposal_generated=status["proposal_generated_this_run"])
    status["maintenance"] = {
        "status": "completed",
        "events": events,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "proposal_generated_this_run": bool(status.get("proposal_generated_this_run")),
    }
    return status


def _load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
