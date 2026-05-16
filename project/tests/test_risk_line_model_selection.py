from __future__ import annotations

from project.risk_line_model_selection import build_risk_line_model_selection


def test_build_risk_line_model_selection_marks_adopt_review_reject():
    backtest = {
        "targets": ["warning_target", "danger_target", "extreme_target"],
        "indicators": {
            "SPY": {
                "family": "price_shock",
                "adverse_direction": "lower",
                "targets": {
                    "warning_target": {
                        "best": {"feature": "level_zscore", "threshold": 0.8, "quantile": 0.3, "f1": 0.52, "precision": 0.5, "recall": 0.54, "false_positive_rate": 0.2, "average_lead_weeks": 2.0},
                        "time_splits": {"average_test_f1": 0.3},
                        "walk_forward": {"average_test_f1": 0.21},
                    },
                    "danger_target": {
                        "best": {"feature": "drawdown_13w", "threshold": -0.02, "quantile": 0.2, "f1": 0.33, "precision": 0.4, "recall": 0.3, "false_positive_rate": 0.1, "average_lead_weeks": 2.0},
                        "time_splits": {"average_test_f1": 0.13},
                        "walk_forward": {"average_test_f1": 0.11},
                    },
                    "extreme_target": {
                        "best": {"feature": "roc_4w", "threshold": -0.04, "quantile": 0.1, "f1": 0.18, "precision": 0.17, "recall": 0.6, "false_positive_rate": 0.08, "average_lead_weeks": 1.4},
                        "time_splits": {"average_test_f1": 0.02},
                        "walk_forward": {"average_test_f1": 0.01},
                    },
                },
            }
        },
    }

    selection = build_risk_line_model_selection(backtest)

    targets = selection["indicators"]["SPY"]["targets"]
    assert targets["warning_target"]["decision"] == "adopt"
    assert targets["warning_target"]["selection_band"] == "core"
    assert targets["danger_target"]["decision"] == "review"
    assert targets["danger_target"]["selection_band"] == "fallback_candidate"
    assert targets["extreme_target"]["decision"] == "reject"
    assert targets["extreme_target"]["selection_band"] == "out_of_band"
