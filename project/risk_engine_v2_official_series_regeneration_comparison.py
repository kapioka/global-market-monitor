from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from project.risk_engine_v2_contract import attach_shadow_diagnostic_contract

SCHEMA_VERSION = "risk_engine_v2.official_series_regeneration_comparison.v1"


def build_official_series_regeneration_comparison(
    before_replay: dict[str, Any],
    after_replay: dict[str, Any],
    *,
    before_review: dict[str, Any] | None = None,
    after_review: dict[str, Any] | None = None,
    before_holdout: dict[str, Any] | None = None,
    after_holdout: dict[str, Any] | None = None,
    before_audit: dict[str, Any] | None = None,
    after_audit: dict[str, Any] | None = None,
    production_invariance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    before_store = _store(before_replay)
    after_store = _store(after_replay)
    cross_artifact_reconciliation = _cross_artifact_reconciliation(after_replay, after_review or {}, after_holdout or {}, after_audit or {})
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "pending",
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "source_change": {
            "before": _store_summary(before_store),
            "after": _store_summary(after_store),
            "changed": _store_summary(before_store) != _store_summary(after_store),
        },
        "replay": {
            "before": _replay_summary(before_replay),
            "after": _replay_summary(after_replay),
        },
        "review": {
            "before": _review_summary(before_review or {}),
            "after": _review_summary(after_review or {}),
        },
        "holdout": {
            "before": _holdout_summary(before_holdout or {}),
            "after": _holdout_summary(after_holdout or {}),
        },
        "holdout_primary_coverage_audit": {
            "before": _audit_summary(before_audit or {}),
            "after": _audit_summary(after_audit or {}),
        },
        "cross_artifact_reconciliation": cross_artifact_reconciliation,
        "production_invariance": _production_invariance_summary(production_invariance or {}),
        "decision": {
            "promotion_allowed": False,
            "reason": "canonical official-series replay regeneration is diagnostic-only",
        },
    }
    payload["status"] = (
        "pass"
        if _comparison_passes(
            before_store,
            after_store,
            cross_artifact_reconciliation,
            production_invariance,
        )
        else "review_required"
    )
    payload["artifact_hash"] = _stable_hash({key: value for key, value in payload.items() if key != "artifact_hash"})
    return attach_shadow_diagnostic_contract(payload, artifact_type="review")


def run_official_series_regeneration_comparison(
    *,
    before_replay_json: str | Path,
    after_replay_json: str | Path = "project/reports/risk_engine_v2_reconstructed_replay.json",
    before_review_json: str | Path | None = None,
    after_review_json: str | Path = "project/reports/risk_engine_v2_replay_review.json",
    before_holdout_json: str | Path | None = None,
    after_holdout_json: str | Path = "project/reports/risk_engine_v2_holdout_validation.json",
    before_audit_json: str | Path | None = None,
    after_audit_json: str | Path = "project/reports/risk_engine_v2_holdout_primary_coverage_audit.json",
    production_invariance_json: str | Path = "project/reports/risk_engine_v2_production_invariance.json",
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    payload = build_official_series_regeneration_comparison(
        _read_json(before_replay_json),
        _read_json(after_replay_json),
        before_review=_read_optional_json(before_review_json),
        after_review=_read_optional_json(after_review_json),
        before_holdout=_read_optional_json(before_holdout_json),
        after_holdout=_read_optional_json(after_holdout_json),
        before_audit=_read_optional_json(before_audit_json),
        after_audit=_read_optional_json(after_audit_json),
        production_invariance=_read_optional_json(production_invariance_json),
    )
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "risk_engine_v2_official_series_regeneration_comparison.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": payload["status"],
        "json_path": str(json_path),
        "source_changed": payload["source_change"]["changed"],
        "cross_artifact_reconciliation": payload["cross_artifact_reconciliation"],
    }


def _store(payload: dict[str, Any]) -> dict[str, Any]:
    return _dict_value(_dict_value(payload, "reconstruction"), "official_series_store")


def _store_summary(store: dict[str, Any]) -> dict[str, Any]:
    return {
        "selection_origin": store.get("selection_origin"),
        "requested_path": store.get("requested_path") or store.get("path"),
        "resolved_path": store.get("resolved_path") or store.get("path"),
        "exists": bool(store.get("exists", store.get("loaded"))),
        "loaded": bool(store.get("loaded")),
        "sha256": store.get("sha256"),
        "row_count": int(store.get("row_count") or 0),
        "required_series_presence": store.get("required_series_presence") or {},
        "series_inventory": store.get("series_inventory") or {},
    }


def _replay_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = _dict_value(payload, "summary")
    reconstruction = _dict_value(payload, "reconstruction")
    coverage = _dict_value(summary, "primary_coverage_summary")
    return {
        "status": payload.get("status"),
        "policy_status": payload.get("policy_status"),
        "affects_final_action": payload.get("affects_final_action"),
        "case_count": int(summary.get("total_cases") or reconstruction.get("case_count") or 0),
        "timeline_case_count": int(summary.get("timeline_case_count") or reconstruction.get("timeline_case_count") or 0),
        "primary_strict_available_cases": int(summary.get("primary_strict_available_cases") or 0),
        "fallback_strict_available_cases": int(summary.get("fallback_strict_available_cases") or 0),
        "primary_coverage_summary": coverage,
        "replay_hash": _stable_hash(payload.get("cases") or []),
    }


def _review_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "case_count": int(payload.get("case_count") or 0),
        "episode_count": int(payload.get("episode_count") or 0),
        "counts": payload.get("counts") or {},
        "weekly_timeline_count": len(payload.get("weekly_timeline") or []),
    }


def _holdout_summary(payload: dict[str, Any]) -> dict[str, Any]:
    holdout = _dict_value(payload, "holdout")
    decision = _dict_value(payload, "decision")
    return {
        "status": payload.get("status"),
        "policy_status": payload.get("policy_status"),
        "holdout_weekly_case_count": int(payload.get("holdout_weekly_case_count") or holdout.get("case_count") or 0),
        "event_holdout_count": int(payload.get("event_holdout_count") or holdout.get("event_count") or 0),
        "promotion_allowed": bool(decision.get("promotion_allowed")),
        "blockers": payload.get("blockers") or decision.get("blockers") or [],
    }


def _audit_summary(payload: dict[str, Any]) -> dict[str, Any]:
    reconciliation = _dict_value(payload, "replay_vs_holdout_reconciliation")
    return {
        "status": payload.get("status"),
        "holdout_weekly_case_count": int(payload.get("holdout_weekly_case_count") or 0),
        "weekly_coverage_counts": payload.get("weekly_coverage_counts") or {},
        "reason_code_counts": payload.get("reason_code_counts") or {},
        "coverage_state_mismatch_count": int(reconciliation.get("coverage_state_mismatch_count") or 0),
        "coverage_field_loss_count": int(reconciliation.get("coverage_field_loss_count") or 0),
        "subset_recomputation_mismatch_count": int(reconciliation.get("subset_recomputation_mismatch_count") or 0),
        "root_causes": payload.get("root_causes") or [],
    }


def _cross_artifact_reconciliation(
    replay: dict[str, Any],
    review: dict[str, Any],
    holdout: dict[str, Any],
    audit: dict[str, Any],
) -> dict[str, Any]:
    replay_cases = len(replay.get("cases") or [])
    weekly_timeline = len(review.get("weekly_timeline") or [])
    holdout_payload = _dict_value(holdout, "holdout")
    holdout_count = int(holdout.get("holdout_weekly_case_count") or holdout_payload.get("case_count") or 0)
    audit_count = int(audit.get("holdout_weekly_case_count") or 0)
    audit_reconciliation = _dict_value(audit, "replay_vs_holdout_reconciliation")
    required_artifacts_present = all((replay, review, holdout, audit))
    artifact_contracts_valid = all(_has_shadow_contract(artifact) for artifact in (replay, review, holdout, audit))
    mismatch_counts_present = all(
        isinstance(audit_reconciliation.get(field), int) and not isinstance(audit_reconciliation.get(field), bool)
        for field in (
            "coverage_state_mismatch_count",
            "coverage_field_loss_count",
            "subset_recomputation_mismatch_count",
        )
    )
    result: dict[str, Any] = {
        "replay_case_count": replay_cases,
        "review_weekly_timeline_count": weekly_timeline,
        "holdout_weekly_case_count": holdout_count,
        "audit_holdout_weekly_case_count": audit_count,
        "review_matches_replay": weekly_timeline == replay_cases,
        "audit_matches_holdout": audit_count == holdout_count,
        "coverage_state_mismatch_count": int(audit_reconciliation.get("coverage_state_mismatch_count") or 0),
        "coverage_field_loss_count": int(audit_reconciliation.get("coverage_field_loss_count") or 0),
        "subset_recomputation_mismatch_count": int(audit_reconciliation.get("subset_recomputation_mismatch_count") or 0),
        "required_artifacts_present": required_artifacts_present,
        "artifact_contracts_valid": artifact_contracts_valid,
        "mismatch_counts_present": mismatch_counts_present,
    }
    result["status"] = (
        "pass"
        if required_artifacts_present
        and artifact_contracts_valid
        and result["review_matches_replay"] is True
        and result["audit_matches_holdout"] is True
        and mismatch_counts_present
        and result["coverage_state_mismatch_count"] == 0
        and result["coverage_field_loss_count"] == 0
        and result["subset_recomputation_mismatch_count"] == 0
        else "fail"
    )
    return result


def _has_shadow_contract(payload: dict[str, Any]) -> bool:
    decision = _dict_value(payload, "decision")
    return bool(
        payload.get("status") == "ok"
        and payload.get("policy_status") == "diagnostic_only_not_promoted"
        and payload.get("affects_final_action") is False
        and decision.get("promotion_allowed") is False
    )


def _production_invariance_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "overall": payload.get("overall"),
        "same_market_snapshot": payload.get("same_market_snapshot"),
        "market_snapshot_comparison": payload.get("market_snapshot_comparison") or {},
        "compared_weekly_count": int(payload.get("compared_weekly_count") or 0),
        "mismatched_count_per_field": payload.get("mismatched_count_per_field") or {},
    }


def _dict_value(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _comparison_passes(
    before_store: dict[str, Any],
    after_store: dict[str, Any],
    cross_artifact_reconciliation: dict[str, Any],
    production_invariance: dict[str, Any] | None,
) -> bool:
    invariance_ok = bool(
        production_invariance
        and production_invariance.get("overall") == "pass"
        and production_invariance.get("same_market_snapshot") is True
    )
    stores_loaded = all(store.get("loaded") is True and store.get("exists") is True for store in (before_store, after_store))
    return bool(stores_loaded and cross_artifact_reconciliation.get("status") == "pass" and invariance_ok)


def _read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_optional_json(path: str | Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    json_path = Path(path)
    if not json_path.exists():
        return None
    return _read_json(json_path)


def _stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare loaded official-series risk_engine_v2 replay regenerations.")
    parser.add_argument("--before-replay-json", required=True)
    parser.add_argument("--after-replay-json", default="project/reports/risk_engine_v2_reconstructed_replay.json")
    parser.add_argument("--before-review-json", default=None)
    parser.add_argument("--after-review-json", default="project/reports/risk_engine_v2_replay_review.json")
    parser.add_argument("--before-holdout-json", default=None)
    parser.add_argument("--after-holdout-json", default="project/reports/risk_engine_v2_holdout_validation.json")
    parser.add_argument("--before-audit-json", default=None)
    parser.add_argument("--after-audit-json", default="project/reports/risk_engine_v2_holdout_primary_coverage_audit.json")
    parser.add_argument("--production-invariance-json", default="project/reports/risk_engine_v2_production_invariance.json")
    parser.add_argument("--reports-dir", default="project/reports")
    args = parser.parse_args()
    print(
        json.dumps(
            run_official_series_regeneration_comparison(
                before_replay_json=args.before_replay_json,
                after_replay_json=args.after_replay_json,
                before_review_json=args.before_review_json,
                after_review_json=args.after_review_json,
                before_holdout_json=args.before_holdout_json,
                after_holdout_json=args.after_holdout_json,
                before_audit_json=args.before_audit_json,
                after_audit_json=args.after_audit_json,
                production_invariance_json=args.production_invariance_json,
                reports_dir=args.reports_dir,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
