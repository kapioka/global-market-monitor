from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_POLICY_STATUS = "diagnostic_only_not_promoted"
ARTIFACT_CONTRACTS: dict[str, dict[str, Any]] = {
    "risk_engine_v2_replay.json": {"status": "ok"},
    "risk_engine_v2_replay_review.json": {"status": "ok"},
    "risk_engine_v2_holdout_validation.json": {"status": "ok"},
    "risk_engine_v2_retention_reconciliation.json": {"status": "pass"},
    "risk_engine_v2_production_invariance.json": {"status": "pass", "overall": "pass"},
    "risk_engine_v2_official_series_regeneration_comparison.json": {"status": "pass"},
    "risk_engine_v2_episode_chronicle.json": {
        "status": "ready",
        "schema_version": "risk_engine_v2.episode_chronicle.v1",
        "implementation_version": "risk_engine_v2.episode_chronicle.implementation.v3",
        "freshness_status": "current",
        "promotion_allowed": False,
    },
}


def verify_artifact(path: Path, expected: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    if not path.is_file():
        return [f"missing artifact: {path}"]

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"invalid JSON: {path}: {exc}"]

    if not isinstance(payload, dict):
        return [f"artifact root must be an object: {path}"]

    if payload.get("policy_status") != EXPECTED_POLICY_STATUS:
        violations.append(f"{path.name}: policy_status must be {EXPECTED_POLICY_STATUS!r}, got {payload.get('policy_status')!r}")
    if payload.get("affects_final_action") is not False:
        violations.append(f"{path.name}: affects_final_action must be false")

    decision = payload.get("decision")
    if not isinstance(decision, dict) or decision.get("promotion_allowed") is not False:
        violations.append(f"{path.name}: decision.promotion_allowed must be false")

    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            violations.append(f"{path.name}: {key} must be {expected_value!r}, got {payload.get(key)!r}")

    return violations


def verify_artifacts(reports_dir: Path) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    violations: list[str] = []
    for filename, expected in ARTIFACT_CONTRACTS.items():
        artifact_violations = verify_artifact(reports_dir / filename, expected)
        results.append(
            {
                "artifact": filename,
                "status": "pass" if not artifact_violations else "fail",
                "violations": artifact_violations,
            }
        )
        violations.extend(artifact_violations)

    return {
        "schema_version": 1,
        "reports_dir": str(reports_dir.resolve()),
        "read_only": True,
        "status": "pass" if not violations else "fail",
        "artifacts": results,
        "violations": violations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the semantic contract of risk_engine_v2 JSON artifacts.")
    parser.add_argument("--reports-dir", type=Path, default=Path("project/reports"))
    args = parser.parse_args()

    result = verify_artifacts(args.reports_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
