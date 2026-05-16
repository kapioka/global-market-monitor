from __future__ import annotations

from pathlib import Path

from project.risk_line_model_registry_report import (
    build_risk_line_model_registry_from_config,
    render_risk_line_model_registry_markdown,
    write_risk_line_model_registry_report,
)


def _fake_registry() -> dict:
    return {
        "indicator_count": 1,
        "live_indicator_count": 1,
        "targets": ["warning_target"],
        "decision_counts": {"adopt": 1, "review": 0, "reject": 0},
        "stage_coverage": {"warning_target": 1, "danger_target": 0, "extreme_target": 0},
        "data_source": "sample",
        "warnings": [],
        "live_models": {
            "SPY": {
                "family": "price_shock",
                "adverse_direction": "lower",
                "targets": {
                    "warning_target": {
                        "decision": "adopt",
                        "reason": "stable_enough",
                        "selected_model": {"feature": "level_zscore", "threshold": 0.9},
                        "metrics": {"split_f1": 0.4, "walk_forward_f1": 0.2},
                    }
                },
            }
        },
        "review_queue": {},
        "rejected_targets": {},
    }


def test_build_risk_line_model_registry_from_config(monkeypatch):
    monkeypatch.setattr(
        "project.risk_line_model_registry_report.build_risk_line_model_selection_from_config",
        lambda config, sample_only=False: {
            "indicator_count": 1,
            "targets": ["warning_target"],
            "decision_counts": {"adopt": 1, "review": 0, "reject": 0},
            "indicators": {
                "SPY": {
                    "family": "price_shock",
                    "adverse_direction": "lower",
                    "targets": {
                        "warning_target": {
                            "decision": "adopt",
                            "reason": "stable_enough",
                            "selected_model": {"feature": "level_zscore", "threshold": 0.9},
                            "metrics": {"split_f1": 0.4, "walk_forward_f1": 0.2},
                        }
                    },
                }
            },
            "data_source": "sample",
            "warnings": [],
        },
    )

    registry = build_risk_line_model_registry_from_config({}, sample_only=True)

    assert registry["live_models"]["SPY"]["targets"]["warning_target"]["decision"] == "adopt"


def test_write_risk_line_model_registry_report(monkeypatch):
    monkeypatch.setattr("project.risk_line_model_registry_report.load_config", lambda path: {"paths": {"reports_dir": r"C:\repo\project\reports"}})
    monkeypatch.setattr("project.risk_line_model_registry_report.build_risk_line_model_registry_from_config", lambda config, sample_only=False: _fake_registry())

    json_path, md_path = write_risk_line_model_registry_report("dummy.yaml", sample_only=False)

    assert Path(json_path).exists()
    assert Path(md_path).exists()


def test_render_risk_line_model_registry_markdown():
    text = render_risk_line_model_registry_markdown(_fake_registry())

    assert "# Risk Line Model Registry" in text
    assert "## Live Models" in text
    assert "level_zscore" in text
