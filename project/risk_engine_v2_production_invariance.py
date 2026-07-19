from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from project.risk_engine_v2_contract import attach_shadow_diagnostic_contract

PRODUCTION_FIELDS = (
    "domain_scores",
    "domain_candidate_stage",
    "domain_confirmed_stage",
    "global_candidate_stage",
    "global_confirmed_stage",
    "domain_persistence_episode_id",
    "domain_persistence_entry_rule",
    "domain_persistence_gap_reset",
    "final_action",
    "buy_readiness_score",
    "production_candidate_ranking",
    "hindenburg_omen_decision_impact",
    "risk_engine_v2_mode",
)


def build_production_invariance_report(baseline_payload: dict[str, Any], post_payload: dict[str, Any]) -> dict[str, Any]:
    market_snapshot_comparison = _market_snapshot_comparison(baseline_payload, post_payload)
    baseline_cases = _case_map(baseline_payload)
    post_cases = _case_map(post_payload)
    common_dates = sorted(set(baseline_cases).intersection(post_cases))
    missing_baseline_dates = sorted(set(baseline_cases).difference(post_cases))
    appended_post_dates = sorted(set(post_cases).difference(baseline_cases))
    last_baseline_date = max(baseline_cases, default=None)
    non_append_post_dates = [date for date in appended_post_dates if last_baseline_date and date <= last_baseline_date]
    mismatches: dict[str, int] = {field: 0 for field in PRODUCTION_FIELDS}
    examples: list[dict[str, Any]] = []
    for date in common_dates:
        left = _production_projection(baseline_cases[date])
        right = _production_projection(post_cases[date])
        for field in PRODUCTION_FIELDS:
            if left.get(field) != right.get(field):
                mismatches[field] += 1
                if len(examples) < 20:
                    examples.append({"date": date, "field": field, "baseline": left.get(field), "post": right.get(field)})
    total_mismatches = sum(mismatches.values())
    invariant = (
        market_snapshot_comparison["status"] == "match"
        and total_mismatches == 0
        and not missing_baseline_dates
        and not non_append_post_dates
        and len(common_dates) == len(baseline_cases)
    )
    payload = {
        "status": "pass" if invariant else "fail",
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "source_replay_type": post_payload.get("replay_type"),
        "schema_version": "risk_engine_v2.production_invariance.v1",
        "compared_weekly_count": len(common_dates),
        "baseline_weekly_count": len(baseline_cases),
        "post_weekly_count": len(post_cases),
        "missing_baseline_dates": missing_baseline_dates,
        "appended_post_dates": appended_post_dates,
        "non_append_post_dates": non_append_post_dates,
        "append_only_extension": bool(appended_post_dates) and invariant,
        "compared_field_list": list(PRODUCTION_FIELDS),
        "mismatched_count_per_field": mismatches,
        "example_mismatches": examples,
        "market_snapshot_comparison": market_snapshot_comparison,
        "same_market_snapshot": market_snapshot_comparison["status"] == "match",
        "baseline_hash": _stable_hash([_production_projection(baseline_cases[date]) for date in sorted(baseline_cases)]),
        "post_hash": _stable_hash([_production_projection(post_cases[date]) for date in sorted(post_cases)]),
        "overall": "pass" if invariant else "fail",
        "decision": {"promotion_allowed": False, "reason": "production invariance comparison is diagnostic-only"},
    }
    return attach_shadow_diagnostic_contract(payload, artifact_type="review")


def run_production_invariance_report(
    baseline_replay_json: str | Path,
    post_replay_json: str | Path = "project/reports/risk_engine_v2_reconstructed_replay.json",
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    baseline_path = Path(baseline_replay_json)
    post_path = Path(post_replay_json)
    if not baseline_path.exists():
        return {"status": "missing_baseline", "baseline_replay_json": str(baseline_path)}
    if not post_path.exists():
        return {"status": "missing_post", "post_replay_json": str(post_path)}
    payload = build_production_invariance_report(
        json.loads(baseline_path.read_text(encoding="utf-8")),
        json.loads(post_path.read_text(encoding="utf-8")),
    )
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "risk_engine_v2_production_invariance.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": payload["status"],
        "json_path": str(json_path),
        "compared_weekly_count": payload["compared_weekly_count"],
        "mismatched_count_per_field": payload["mismatched_count_per_field"],
        "market_snapshot_comparison": payload["market_snapshot_comparison"],
        "same_market_snapshot": payload["same_market_snapshot"],
        "overall": payload["overall"],
    }


def _case_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(case.get("date")): case for case in payload.get("cases", []) or [] if isinstance(case, dict) and case.get("date")}


def _market_snapshot_comparison(baseline_payload: dict[str, Any], post_payload: dict[str, Any]) -> dict[str, Any]:
    baseline_hash = _market_snapshot_hash(baseline_payload)
    post_hash = _market_snapshot_hash(post_payload)
    if baseline_hash is None and post_hash is None:
        status = "missing_both"
    elif baseline_hash is None:
        status = "missing_baseline"
    elif post_hash is None:
        status = "missing_post"
    else:
        status = "match" if baseline_hash == post_hash else "mismatch"
    return {"status": status, "baseline_sha256": baseline_hash, "post_sha256": post_hash}


def _market_snapshot_hash(payload: dict[str, Any]) -> str | None:
    reconstruction = payload.get("reconstruction")
    if not isinstance(reconstruction, dict):
        return None
    market_snapshot = reconstruction.get("market_snapshot")
    if not isinstance(market_snapshot, dict):
        return None
    value = market_snapshot.get("sha256")
    return str(value) if value else None


def _production_projection(case: dict[str, Any]) -> dict[str, Any]:
    raw_decision = case.get("buy_decision_card")
    decision: dict[str, Any] = raw_decision if isinstance(raw_decision, dict) else {}
    raw_hindenburg = case.get("hindenburg_omen")
    hindenburg: dict[str, Any] = raw_hindenburg if isinstance(raw_hindenburg, dict) else {}
    return {
        "date": case.get("date"),
        "domain_scores": case.get("domain_scores"),
        "domain_candidate_stage": case.get("domain_candidate_stage"),
        "domain_confirmed_stage": case.get("domain_confirmed_stage"),
        "global_candidate_stage": case.get("global_candidate_stage") or case.get("domain_candidate_stage"),
        "global_confirmed_stage": case.get("global_confirmed_stage") or case.get("domain_confirmed_stage"),
        "domain_persistence_episode_id": case.get("domain_persistence_episode_id"),
        "domain_persistence_entry_rule": case.get("domain_persistence_entry_rule"),
        "domain_persistence_gap_reset": case.get("domain_persistence_gap_reset"),
        "final_action": decision.get("final_action") or case.get("final_action"),
        "buy_readiness_score": case.get("buy_readiness_score"),
        "production_candidate_ranking": case.get("production_candidate_ranking"),
        "hindenburg_omen_decision_impact": hindenburg.get("decision_impact") or case.get("hindenburg_omen_decision_impact"),
        "risk_engine_v2_mode": case.get("risk_engine_v2_mode", "shadow"),
    }


def _stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare risk_engine_v2 production-field invariance.")
    parser.add_argument("--baseline-replay-json", required=True)
    parser.add_argument("--post-replay-json", default="project/reports/risk_engine_v2_reconstructed_replay.json")
    parser.add_argument("--reports-dir", default="project/reports")
    args = parser.parse_args()
    print(
        json.dumps(
            run_production_invariance_report(args.baseline_replay_json, args.post_replay_json, args.reports_dir),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
