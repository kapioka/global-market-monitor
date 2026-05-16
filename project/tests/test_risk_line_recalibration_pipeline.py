from __future__ import annotations

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
