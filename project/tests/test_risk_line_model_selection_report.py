from __future__ import annotations

import json
from pathlib import Path

from project.risk_line_model_selection_report import (
    build_risk_line_model_selection_from_config,
    render_risk_line_model_selection_markdown,
    write_risk_line_model_selection_report,
)


def _fake_selection():
    return {
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
                        "selected_model": {"feature": "level_zscore", "threshold": 0.8, "quantile": 0.3},
                        "metrics": {"full_f1": 0.52, "split_f1": 0.3, "walk_forward_f1": 0.21, "precision": 0.5, "recall": 0.54},
                    }
                },
            }
        },
        "data_source": "yfinance",
        "warnings": [],
    }


def test_build_risk_line_model_selection_from_config(monkeypatch):
    monkeypatch.setattr("project.risk_line_model_selection_report.build_risk_line_backtest_from_config", lambda config, sample_only=False: {
        "targets": ["warning_target"],
        "data_source": "sample",
        "warnings": [],
        "indicators": {
            "SPY": {
                "family": "price_shock",
                "adverse_direction": "lower",
                "targets": {
                    "warning_target": {
                        "best": {"feature": "level_zscore", "threshold": 0.8, "quantile": 0.3, "f1": 0.52, "precision": 0.5, "recall": 0.54, "false_positive_rate": 0.2, "average_lead_weeks": 2.0},
                        "time_splits": {"average_test_f1": 0.3},
                        "walk_forward": {"average_test_f1": 0.21},
                    }
                },
            }
        },
    })
    selection = build_risk_line_model_selection_from_config({}, sample_only=True)
    assert selection["indicator_count"] == 1
    assert selection["indicators"]["SPY"]["targets"]["warning_target"]["decision"] == "adopt"


def test_write_risk_line_model_selection_report(monkeypatch):
    monkeypatch.setattr("project.risk_line_model_selection_report.load_config", lambda path: {"paths": {"reports_dir": r"C:\\repo\\project\\reports"}})
    monkeypatch.setattr("project.risk_line_model_selection_report.build_risk_line_model_selection_from_config", lambda config, sample_only=False: _fake_selection())
    monkeypatch.setattr(Path, "mkdir", lambda self, parents=False, exist_ok=False: None)
    writes = {}
    monkeypatch.setattr(Path, "write_text", lambda self, text, encoding='utf-8': writes.setdefault(str(self), text) or len(text))
    json_path, md_path = write_risk_line_model_selection_report("dummy.yaml", sample_only=False)
    assert str(json_path) in writes
    assert str(md_path) in writes
    assert json.loads(writes[str(json_path)])["indicator_count"] == 1
    assert "Risk Line Model Selection" in writes[str(md_path)]


def test_render_risk_line_model_selection_markdown():
    text = render_risk_line_model_selection_markdown(_fake_selection())
    assert "# Risk Line Model Selection" in text
    assert "- decision: adopt" in text
    assert "- feature: level_zscore" in text
