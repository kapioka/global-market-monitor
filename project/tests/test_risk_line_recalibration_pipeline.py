from __future__ import annotations

import json

from project.risk_line_recalibration_pipeline import (
    build_risk_line_recalibration_payload,
    render_risk_line_recalibration_summary_markdown,
    render_risk_line_threshold_diff_markdown,
)


def test_render_risk_line_recalibration_outputs():
    summary = {
        "data_source": "sample",
        "active_version": "a1",
        "proposed_version": "p1",
        "active_indicator_count": 1,
        "proposed_indicator_count": 1,
        "decision_counts": {"adopt": 1, "fallback_review": 0, "fallback_guarded": 0},
        "diff_summary": {"added": 0, "removed": 0, "changed": 1, "unchanged": 0},
        "warnings": [],
    }
    diff = {
        "active_version": "a1",
        "proposed_version": "p1",
        "summary": {"added": 0, "removed": 0, "changed": 1, "unchanged": 0},
        "changes": [{"ticker": "SPY", "stage": "warning", "change_type": "changed", "active": {"feature": "drawdown_13w", "direction": "lower", "threshold": -0.02}, "proposed": {"feature": "drawdown_13w", "direction": "lower", "threshold": -0.03}}],
    }

    summary_text = render_risk_line_recalibration_summary_markdown(summary)
    diff_text = render_risk_line_threshold_diff_markdown(diff)

    assert "# Risk Line Recalibration Summary" in summary_text
    assert "# Risk Line Threshold Diff" in diff_text
    assert "SPY / warning" in diff_text


def test_build_risk_line_recalibration_payload(monkeypatch):
    monkeypatch.setattr(
        "project.risk_line_recalibration_pipeline.build_risk_line_reality_checked_report_from_config",
        lambda config, sample_only=False: {
            "data_source": "sample",
            "warnings": [],
            "decision_counts": {"adopt": 1, "fallback_review": 0, "fallback_guarded": 0},
            "indicators": {
                "SPY": {
                    "adverse_direction": "lower",
                    "targets": {
                        "warning_target": {
                            "decision": "adopt",
                            "selection_mode": "adopt",
                            "coverage_forced": False,
                            "reason": "passes_backtest_and_actual_value_check",
                            "selected_model": {"feature": "drawdown_13w", "threshold": -0.02, "quantile": 0.3},
                            "metrics": {"full_f1": 0.5},
                            "actual_value_check": {"status": "pass", "reasons": []},
                            "raw_value_reference": [],
                            "frequency_profile": {},
                        }
                    },
                }
            },
        },
    )

    payload = build_risk_line_recalibration_payload({"paths": {"reports_dir": r"C:\repo\project\reports"}}, sample_only=True)

    assert payload["summary"]["data_source"] == "sample"
    assert "SPY" in payload["proposed_thresholds"]["indicators"]


def test_write_recalibration_outputs_does_not_update_proposed_by_default(tmp_path, monkeypatch):
    reports_dir = tmp_path / "reports"
    proposed_path = tmp_path / "risk_line_thresholds_proposed.json"
    writes = []
    payload = {
        "summary": {"data_source": "sample", "active_version": "a1", "proposed_version": "p1", "decision_counts": {}, "diff_summary": {}},
        "diff": {"active_version": "a1", "proposed_version": "p1", "summary": {}, "changes": []},
        "proposed_thresholds": {"threshold_set": {"version": "p1"}, "indicators": {}},
    }

    monkeypatch.setattr("project.risk_line_recalibration_pipeline.load_config", lambda path: {"paths": {"reports_dir": str(reports_dir)}})
    monkeypatch.setattr("project.risk_line_recalibration_pipeline.build_risk_line_recalibration_payload", lambda config, sample_only=False: payload)
    monkeypatch.setattr("project.risk_line_recalibration_pipeline.PROPOSED_THRESHOLDS_PATH", proposed_path)
    monkeypatch.setattr("project.risk_line_recalibration_pipeline.write_threshold_payload", lambda path, data: writes.append((path, data)))

    from project.risk_line_recalibration_pipeline import write_risk_line_recalibration_outputs

    outputs = write_risk_line_recalibration_outputs(tmp_path / "config.yaml", sample_only=True)

    assert outputs["proposed_json"] is None
    assert writes == []
    assert outputs["proposed_snapshot_json"].exists()
    assert json.loads(outputs["proposed_snapshot_json"].read_text(encoding="utf-8"))["threshold_set"]["version"] == "p1"


def test_write_recalibration_outputs_updates_proposed_with_explicit_flag(tmp_path, monkeypatch):
    reports_dir = tmp_path / "reports"
    proposed_path = tmp_path / "risk_line_thresholds_proposed.json"
    writes = []
    payload = {
        "summary": {"data_source": "sample", "active_version": "a1", "proposed_version": "p1", "decision_counts": {}, "diff_summary": {}},
        "diff": {"active_version": "a1", "proposed_version": "p1", "summary": {}, "changes": []},
        "proposed_thresholds": {"threshold_set": {"version": "p1"}, "indicators": {}},
    }

    monkeypatch.setattr("project.risk_line_recalibration_pipeline.load_config", lambda path: {"paths": {"reports_dir": str(reports_dir)}})
    monkeypatch.setattr("project.risk_line_recalibration_pipeline.build_risk_line_recalibration_payload", lambda config, sample_only=False: payload)
    monkeypatch.setattr("project.risk_line_recalibration_pipeline.PROPOSED_THRESHOLDS_PATH", proposed_path)
    monkeypatch.setattr("project.risk_line_recalibration_pipeline.write_threshold_payload", lambda path, data: writes.append((path, data)))

    from project.risk_line_recalibration_pipeline import write_risk_line_recalibration_outputs

    outputs = write_risk_line_recalibration_outputs(tmp_path / "config.yaml", write_proposed=True)

    assert outputs["proposed_json"] == proposed_path
    assert writes == [(proposed_path, payload["proposed_thresholds"])]
