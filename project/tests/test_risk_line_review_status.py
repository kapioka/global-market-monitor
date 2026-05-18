from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from project.risk_line_review_status import build_risk_line_review_status, run_periodic_risk_line_maintenance


def test_build_risk_line_review_status_marks_due_and_recommends_review():
    status = build_risk_line_review_status(
        active_threshold_payload={"threshold_set": {"version": "v1", "generated_at": "2025-12-01T00:00:00+09:00"}},
        drift_snapshot={"summary": {"review_count": 0, "watch_count": 0, "review_targets": []}},
        recalibration_diff={"summary": {"changed": 0, "added": 0, "removed": 0}},
        recalibration_policy={"cadence_days": 90, "warning_days": 14},
        as_of=datetime(2026, 4, 5, tzinfo=timezone.utc),
    )
    assert status["due_for_recalibration"] is True
    assert status["review_recommended"] is True
    assert status["status"] == "review"


def test_build_risk_line_review_status_marks_watch_when_near_due():
    status = build_risk_line_review_status(
        active_threshold_payload={"threshold_set": {"version": "v1", "generated_at": "2026-01-10T00:00:00+00:00"}},
        drift_snapshot={"summary": {"review_count": 0, "watch_count": 1, "review_targets": []}},
        recalibration_diff={"summary": {"changed": 0, "added": 0, "removed": 0}},
        recalibration_policy={"cadence_days": 90, "warning_days": 14},
        as_of=datetime(2026, 4, 5, tzinfo=timezone.utc),
    )
    assert status["due_for_recalibration"] is False
    assert status["status"] == "watch"
    assert status["review_recommended"] is False


def test_run_periodic_risk_line_maintenance_generates_proposal_when_due(monkeypatch):
    calls = {"drift": 0, "recal": 0}
    monkeypatch.setattr("project.risk_line_review_status.load_config", lambda path: {
        "paths": {"reports_dir": r"C:\repo\project\reports"},
        "risk_line_recalibration": {
            "refresh_drift_on_run": True,
            "auto_generate_proposal": True,
            "generate_on_drift_review": True,
            "cadence_days": 90,
            "warning_days": 14,
        },
    })
    monkeypatch.setattr("project.risk_line_review_status.load_threshold_payload", lambda path=None: {"threshold_set": {"version": "v1", "generated_at": "2025-12-01T00:00:00+00:00"}})
    monkeypatch.setattr("project.risk_line_review_status.write_risk_line_threshold_drift_report", lambda config_path, sample_only=False: calls.__setitem__("drift", calls["drift"] + 1))
    monkeypatch.setattr("project.risk_line_review_status.load_risk_line_review_status", lambda reports_dir, active_threshold_payload, recalibration_policy=None, as_of=None: {
        "due_for_recalibration": True,
        "drift_review_count": 0,
        "status": "review",
        "review_recommended": True,
        "reasons": ["recalibration_due:120d"],
    })
    monkeypatch.setattr(
        "project.risk_line_review_status.write_risk_line_recalibration_outputs",
        lambda config_path, sample_only=False, write_proposed=False: calls.__setitem__("recal", calls["recal"] + 1)
        or {"proposed_json": None, "proposed_snapshot_json": Path("snapshot.json")},
    )

    status = run_periodic_risk_line_maintenance(Path("config.yaml"), sample_only=False)

    assert calls == {"drift": 1, "recal": 1}
    assert status["proposal_generated_this_run"] is True
    assert status["proposed_thresholds_written"] is False
    assert status["maintenance"]["status"] == "completed"
    assert len(status["maintenance"]["events"]) >= 4


def test_run_periodic_risk_line_maintenance_never_writes_proposed_for_sample_only(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "project.risk_line_review_status.load_config",
        lambda path: {
            "paths": {"reports_dir": r"C:\repo\project\reports"},
            "risk_line_recalibration": {
                "refresh_drift_on_run": False,
                "auto_generate_proposal": True,
                "write_proposed_thresholds": True,
                "cadence_days": 90,
            },
        },
    )
    monkeypatch.setattr("project.risk_line_review_status.load_threshold_payload", lambda path=None: {"threshold_set": {"version": "v1", "generated_at": "2025-12-01T00:00:00+00:00"}})
    monkeypatch.setattr(
        "project.risk_line_review_status.load_risk_line_review_status",
        lambda reports_dir, active_threshold_payload, recalibration_policy=None, as_of=None: {
            "due_for_recalibration": True,
            "drift_review_count": 0,
            "status": "review",
            "review_recommended": True,
            "reasons": ["recalibration_due:120d"],
        },
    )

    def fake_write(config_path, sample_only=False, write_proposed=False):
        seen["write_proposed"] = write_proposed
        return {"proposed_json": None, "proposed_snapshot_json": Path("snapshot.json")}

    monkeypatch.setattr("project.risk_line_review_status.write_risk_line_recalibration_outputs", fake_write)

    status = run_periodic_risk_line_maintenance(Path("config.yaml"), sample_only=True)

    assert seen["write_proposed"] is False
    assert status["proposed_thresholds_written"] is False
