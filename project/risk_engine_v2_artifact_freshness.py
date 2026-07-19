from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

DIAGNOSTIC_POLICY_STATUS = "diagnostic_only_not_promoted"
DIAGNOSTIC_ARTIFACTS = {
    "reconstructed_replay": "risk_engine_v2_reconstructed_replay.json",
    "replay_review": "risk_engine_v2_replay_review.json",
    "holdout_validation": "risk_engine_v2_holdout_validation.json",
    "root_cause": "risk_engine_v2_root_cause.json",
    "retention_reconciliation": "risk_engine_v2_retention_reconciliation.json",
    "production_invariance": "risk_engine_v2_production_invariance.json",
    "holdout_primary_coverage_audit": "risk_engine_v2_holdout_primary_coverage_audit.json",
}


def inspect_risk_engine_v2_artifact_freshness(
    *,
    reports_dir: str | Path,
    config_path: str | Path,
    as_of: str | date | datetime,
    max_age_days: int = 3,
) -> dict[str, Any]:
    """Inspect existing diagnostic files without mutating artifacts or source state."""
    if max_age_days < 0:
        raise ValueError("max_age_days must be non-negative")

    as_of_date = _parse_date(as_of, field_name="as_of")
    source_contract = _inspect_source_contract(Path(config_path))
    artifacts = [
        _inspect_artifact(name, Path(reports_dir) / filename, as_of_date, max_age_days) for name, filename in DIAGNOSTIC_ARTIFACTS.items()
    ]
    consistency = _artifact_consistency(artifacts)
    snapshot = _artifact_snapshot(artifacts, consistency)
    return {
        "schema_version": "risk_engine_v2.artifact_freshness.v1",
        "read_only": True,
        "network_access": False,
        "as_of_date": as_of_date.isoformat(),
        "max_age_days": max_age_days,
        "source_contract": source_contract,
        "artifact_snapshot": snapshot,
        "artifact_consistency": consistency,
        "artifacts": artifacts,
    }


def _inspect_source_contract(config_path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(config_path),
        "role": "current_source_contract",
        "expected_mode": "shadow",
    }
    if not config_path.exists():
        return {**result, "status": "missing_config", "mode": None}
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        return {**result, "status": "malformed_config", "mode": None, "error": str(error)}
    if not isinstance(raw, dict):
        return {**result, "status": "malformed_config", "mode": None, "error": "config root must be a mapping"}
    settings = raw.get("risk_engine_v2")
    if not isinstance(settings, dict):
        return {**result, "status": "missing_risk_engine_v2_config", "mode": None}
    mode = settings.get("mode")
    return {
        **result,
        "status": "shadow_contract" if mode == "shadow" else "unexpected_mode",
        "mode": mode,
        "policy_status_requirement": DIAGNOSTIC_POLICY_STATUS,
        "promotion_allowed_requirement": False,
    }


def _inspect_artifact(name: str, path: Path, as_of_date: date, max_age_days: int) -> dict[str, Any]:
    result: dict[str, Any] = {"name": name, "path": str(path)}
    if not path.exists():
        return {**result, "status": "missing", "freshness_status": "missing", "generation_status": "unknown"}
    try:
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return {**result, "status": "malformed", "freshness_status": "unknown", "generation_status": "unknown", "error": str(error)}
    if not isinstance(raw, dict):
        return {
            **result,
            "status": "malformed",
            "freshness_status": "unknown",
            "generation_status": "unknown",
            "error": "artifact root must be a JSON object",
        }

    generated_at = raw.get("generated_at")
    if generated_at is None:
        evidence_date = modified_at.date()
        generation_status = "file_modified_at"
        generation_value = modified_at.isoformat()
    else:
        try:
            evidence_date = _parse_date(generated_at, field_name="generated_at")
        except ValueError as error:
            return {
                **result,
                "status": "parsed",
                "freshness_status": "unknown",
                "generation_status": "malformed",
                "generated_at": generated_at,
                "file_modified_at": modified_at.isoformat(),
                "error": str(error),
            }
        generation_status = "payload_generated_at"
        generation_value = str(generated_at)

    age_days = (as_of_date - evidence_date).days
    freshness_status = "fresh" if 0 <= age_days <= max_age_days else "stale"
    if age_days < 0:
        freshness_status = "future_dated"
    raw_decision = raw.get("decision")
    decision: dict[str, Any] = raw_decision if isinstance(raw_decision, dict) else {}
    return {
        **result,
        "status": "parsed",
        "generation_status": generation_status,
        "generation_value": generation_value,
        "file_modified_at": modified_at.isoformat(),
        "evidence_date": evidence_date.isoformat(),
        "age_days": age_days,
        "freshness_status": freshness_status,
        "policy_status": raw.get("policy_status"),
        "affects_final_action": raw.get("affects_final_action"),
        "promotion_allowed": decision.get("promotion_allowed"),
        "case_count": _case_count(name, raw),
    }


def _artifact_snapshot(artifacts: list[dict[str, Any]], consistency: dict[str, Any]) -> dict[str, Any]:
    statuses = {str(artifact["status"]) for artifact in artifacts}
    freshness = {str(artifact["freshness_status"]) for artifact in artifacts}
    if statuses != {"parsed"} or "unknown" in freshness or "missing" in freshness:
        status = "incomplete"
    elif "future_dated" in freshness:
        status = "future_dated"
    elif consistency["status"] != "consistent":
        status = "inconsistent"
    elif "stale" in freshness:
        status = "historical"
    else:
        status = "current"
    return {
        "role": "historical_artifact_snapshot",
        "status": status,
        "is_current_snapshot": status == "current",
        "artifact_count": len(artifacts),
        "fresh_artifact_count": sum(artifact.get("freshness_status") == "fresh" for artifact in artifacts),
        "stale_artifact_count": sum(artifact.get("freshness_status") == "stale" for artifact in artifacts),
    }


def _artifact_consistency(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    missing_or_malformed = [artifact["name"] for artifact in artifacts if artifact["status"] != "parsed"]
    policy_violations: list[dict[str, Any]] = []
    for artifact in artifacts:
        if artifact["status"] != "parsed":
            continue
        if artifact.get("policy_status") != DIAGNOSTIC_POLICY_STATUS:
            policy_violations.append({"artifact": artifact["name"], "field": "policy_status", "value": artifact.get("policy_status")})
        if artifact.get("affects_final_action") is not False:
            policy_violations.append(
                {"artifact": artifact["name"], "field": "affects_final_action", "value": artifact.get("affects_final_action")}
            )
        if artifact.get("promotion_allowed") is not False:
            policy_violations.append(
                {"artifact": artifact["name"], "field": "promotion_allowed", "value": artifact.get("promotion_allowed")}
            )
    by_name = {str(artifact["name"]): artifact for artifact in artifacts}
    reconciliations = [
        _reconcile("replay_review_timeline", by_name.get("reconstructed_replay"), by_name.get("replay_review")),
        _reconcile("holdout_audit_case_count", by_name.get("holdout_validation"), by_name.get("holdout_primary_coverage_audit")),
    ]
    reconciliation_failures = [row for row in reconciliations if row["status"] != "match"]
    if missing_or_malformed:
        status = "incomplete"
    elif policy_violations or reconciliation_failures:
        status = "inconsistent"
    else:
        status = "consistent"
    return {
        "status": status,
        "missing_or_malformed": missing_or_malformed,
        "policy_violations": policy_violations,
        "reconciliations": reconciliations,
    }


def _reconcile(name: str, left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    if not left or not right or left.get("status") != "parsed" or right.get("status") != "parsed":
        return {"name": name, "status": "unavailable", "left": None, "right": None}
    left_count = left.get("case_count")
    right_count = right.get("case_count")
    if left_count is None or right_count is None:
        return {"name": name, "status": "unavailable", "left": left_count, "right": right_count}
    return {"name": name, "status": "match" if left_count == right_count else "mismatch", "left": left_count, "right": right_count}


def _case_count(name: str, payload: dict[str, Any]) -> int | None:
    if name == "reconstructed_replay":
        cases = payload.get("cases")
        return len(cases) if isinstance(cases, list) else None
    if name == "replay_review":
        timeline = payload.get("weekly_timeline")
        return len(timeline) if isinstance(timeline, list) else None
    if name == "holdout_validation":
        direct = payload.get("holdout_weekly_case_count")
        if isinstance(direct, int):
            return direct
        holdout = payload.get("holdout")
        value = holdout.get("case_count") if isinstance(holdout, dict) else None
        return value if isinstance(value, int) else None
    if name == "holdout_primary_coverage_audit":
        value = payload.get("holdout_weekly_case_count")
        return value if isinstance(value, int) else None
    return None


def _parse_date(value: str | date | datetime, *, field_name: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO-8601 date or datetime")
    text = value.strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text)
        except ValueError as error:
            raise ValueError(f"{field_name} must be an ISO-8601 date or datetime") from error


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect existing risk_engine_v2 diagnostic artifact freshness without modifying files.")
    parser.add_argument("--reports-dir", default="project/reports")
    parser.add_argument("--config", default="project/config.yaml")
    parser.add_argument("--as-of", required=True, help="ISO-8601 date used for deterministic freshness evaluation")
    parser.add_argument("--max-age-days", type=int, default=3)
    args = parser.parse_args()
    result = inspect_risk_engine_v2_artifact_freshness(
        reports_dir=args.reports_dir,
        config_path=args.config,
        as_of=args.as_of,
        max_age_days=args.max_age_days,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
