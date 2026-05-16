from __future__ import annotations

from pathlib import Path

from project.risk_line_reality_check_report import render_risk_line_reality_checked_markdown


def test_render_risk_line_reality_checked_markdown():
    report = {
        "data_source": "sample",
        "indicator_count": 1,
        "decision_counts": {"adopt": 1, "fallback_review": 0, "fallback_guarded": 0},
        "warnings": [],
        "indicators": {
            "SPY": {
                "family": "price_shock",
                "adverse_direction": "lower",
                "targets": {
                    "warning_target": {
                        "decision": "adopt",
                        "selection_mode": "adopt",
                        "coverage_forced": False,
                        "reason": "passes_backtest_and_actual_value_check",
                        "selected_model": {"feature": "roc_4w", "threshold": -0.03, "quantile": 0.2},
                        "metrics": {"full_f1": 0.5, "precision": 0.4, "false_positive_rate": 0.1},
                        "actual_value_check": {
                            "status": "pass",
                            "reasons": [],
                            "anchors": [{"metric": "roc_4w", "true_positive_median": -0.04, "true_positive_p25": -0.05, "true_positive_p75": -0.03, "historical_percentile": 0.12, "severity_score": 0.88}],
                        },
                        "frequency_profile": {"predicted_count": 4, "coverage": 0.2, "true_positive_count": 2},
                    }
                },
            }
        },
    }
    text = render_risk_line_reality_checked_markdown(report)
    assert "# Risk Line Reality-Checked Thresholds" in text
    assert "anchor roc_4w" in text
