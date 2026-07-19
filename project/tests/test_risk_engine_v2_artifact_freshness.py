from __future__ import annotations

import json
from pathlib import Path

from project.risk_engine_v2_artifact_freshness import DIAGNOSTIC_ARTIFACTS, inspect_risk_engine_v2_artifact_freshness


def _write_config(path: Path, *, mode: str = "shadow") -> None:
    path.write_text(f"risk_engine_v2:\n  mode: {mode}\n", encoding="utf-8")


def _artifact_payload(name: str, *, generated_at: str = "2026-07-10T07:30:00") -> dict:
    payload = {
        "generated_at": generated_at,
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "decision": {"promotion_allowed": False},
    }
    if name == "reconstructed_replay":
        payload["cases"] = [{"date": "2026-07-03"}, {"date": "2026-07-10"}]
    elif name == "replay_review":
        payload["weekly_timeline"] = [{"date": "2026-07-03"}, {"date": "2026-07-10"}]
    elif name in {"holdout_validation", "holdout_primary_coverage_audit"}:
        payload["holdout_weekly_case_count"] = 1
    return payload


def _write_complete_artifacts(reports_dir: Path, *, generated_at: str = "2026-07-10T07:30:00") -> None:
    reports_dir.mkdir()
    for name, filename in DIAGNOSTIC_ARTIFACTS.items():
        (reports_dir / filename).write_text(json.dumps(_artifact_payload(name, generated_at=generated_at)), encoding="utf-8")


def test_preflight_reports_current_consistent_snapshot_without_writing_files(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    reports_dir = tmp_path / "reports"
    _write_config(config_path)
    _write_complete_artifacts(reports_dir)
    before = {path.name: path.read_text(encoding="utf-8") for path in reports_dir.iterdir()}

    result = inspect_risk_engine_v2_artifact_freshness(
        reports_dir=reports_dir,
        config_path=config_path,
        as_of="2026-07-10",
        max_age_days=1,
    )

    assert result["read_only"] is True
    assert result["network_access"] is False
    assert result["source_contract"]["status"] == "shadow_contract"
    assert result["artifact_snapshot"]["status"] == "current"
    assert result["artifact_snapshot"]["is_current_snapshot"] is True
    assert result["artifact_consistency"]["status"] == "consistent"
    assert {path.name: path.read_text(encoding="utf-8") for path in reports_dir.iterdir()} == before


def test_preflight_distinguishes_current_source_contract_from_historical_snapshot(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    reports_dir = tmp_path / "reports"
    _write_config(config_path)
    _write_complete_artifacts(reports_dir, generated_at="2026-07-01T07:30:00")

    result = inspect_risk_engine_v2_artifact_freshness(
        reports_dir=reports_dir,
        config_path=config_path,
        as_of="2026-07-10",
        max_age_days=3,
    )

    assert result["source_contract"]["status"] == "shadow_contract"
    assert result["artifact_snapshot"]["status"] == "historical"
    assert result["artifact_snapshot"]["is_current_snapshot"] is False
    assert result["artifact_snapshot"]["stale_artifact_count"] == len(DIAGNOSTIC_ARTIFACTS)


def test_preflight_reports_future_dated_snapshot(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    reports_dir = tmp_path / "reports"
    _write_config(config_path)
    _write_complete_artifacts(reports_dir, generated_at="2026-07-11T07:30:00")

    result = inspect_risk_engine_v2_artifact_freshness(
        reports_dir=reports_dir,
        config_path=config_path,
        as_of="2026-07-10",
    )

    assert result["artifact_snapshot"]["status"] == "future_dated"
    assert all(artifact["freshness_status"] == "future_dated" for artifact in result["artifacts"])


def test_preflight_reports_missing_and_malformed_artifacts(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    reports_dir = tmp_path / "reports"
    _write_config(config_path)
    reports_dir.mkdir()
    first_name, first_filename = next(iter(DIAGNOSTIC_ARTIFACTS.items()))
    (reports_dir / first_filename).write_text("not json", encoding="utf-8")

    result = inspect_risk_engine_v2_artifact_freshness(
        reports_dir=reports_dir,
        config_path=config_path,
        as_of="2026-07-10",
    )

    statuses = {artifact["name"]: artifact["status"] for artifact in result["artifacts"]}
    assert statuses[first_name] == "malformed"
    assert result["artifact_snapshot"]["status"] == "incomplete"
    assert first_name in result["artifact_consistency"]["missing_or_malformed"]


def test_preflight_reports_policy_and_reconciliation_mismatches(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    reports_dir = tmp_path / "reports"
    _write_config(config_path)
    _write_complete_artifacts(reports_dir)
    replay_path = reports_dir / DIAGNOSTIC_ARTIFACTS["reconstructed_replay"]
    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    replay["decision"]["promotion_allowed"] = True
    replay["cases"] = [{"date": "2026-07-10"}]
    replay_path.write_text(json.dumps(replay), encoding="utf-8")

    result = inspect_risk_engine_v2_artifact_freshness(
        reports_dir=reports_dir,
        config_path=config_path,
        as_of="2026-07-10",
    )

    assert result["artifact_consistency"]["status"] == "inconsistent"
    assert result["artifact_snapshot"]["status"] == "inconsistent"
    assert result["artifact_consistency"]["policy_violations"] == [
        {"artifact": "reconstructed_replay", "field": "promotion_allowed", "value": True}
    ]
    assert result["artifact_consistency"]["reconciliations"][0]["status"] == "mismatch"


def test_preflight_requires_root_cause_artifact(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    reports_dir = tmp_path / "reports"
    _write_config(config_path)
    _write_complete_artifacts(reports_dir)
    (reports_dir / DIAGNOSTIC_ARTIFACTS["root_cause"]).unlink()

    result = inspect_risk_engine_v2_artifact_freshness(
        reports_dir=reports_dir,
        config_path=config_path,
        as_of="2026-07-10",
    )

    assert result["artifact_snapshot"]["status"] == "incomplete"
    assert "root_cause" in result["artifact_consistency"]["missing_or_malformed"]


def test_preflight_fails_closed_when_policy_declarations_are_missing(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    reports_dir = tmp_path / "reports"
    _write_config(config_path)
    _write_complete_artifacts(reports_dir)
    replay_path = reports_dir / DIAGNOSTIC_ARTIFACTS["reconstructed_replay"]
    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    replay.pop("policy_status")
    replay.pop("affects_final_action")
    replay["decision"].pop("promotion_allowed")
    replay_path.write_text(json.dumps(replay), encoding="utf-8")

    result = inspect_risk_engine_v2_artifact_freshness(
        reports_dir=reports_dir,
        config_path=config_path,
        as_of="2026-07-10",
    )

    assert result["artifact_snapshot"]["status"] == "inconsistent"
    assert result["artifact_consistency"]["policy_violations"] == [
        {"artifact": "reconstructed_replay", "field": "policy_status", "value": None},
        {"artifact": "reconstructed_replay", "field": "affects_final_action", "value": None},
        {"artifact": "reconstructed_replay", "field": "promotion_allowed", "value": None},
    ]


def test_preflight_fails_closed_when_reconciliation_count_is_unavailable(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    reports_dir = tmp_path / "reports"
    _write_config(config_path)
    _write_complete_artifacts(reports_dir)
    review_path = reports_dir / DIAGNOSTIC_ARTIFACTS["replay_review"]
    review = json.loads(review_path.read_text(encoding="utf-8"))
    review.pop("weekly_timeline")
    review_path.write_text(json.dumps(review), encoding="utf-8")

    result = inspect_risk_engine_v2_artifact_freshness(
        reports_dir=reports_dir,
        config_path=config_path,
        as_of="2026-07-10",
    )

    assert result["artifact_consistency"]["status"] == "inconsistent"
    assert result["artifact_consistency"]["reconciliations"][0]["status"] == "unavailable"
