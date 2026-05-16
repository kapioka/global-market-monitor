from __future__ import annotations

from project.risk_line_model_registry import build_risk_line_model_registry


def test_build_risk_line_model_registry_splits_live_review_reject():
    selection = {
        "indicator_count": 2,
        "targets": ["warning_target", "danger_target", "extreme_target"],
        "decision_counts": {"adopt": 1, "review": 1, "reject": 1},
        "data_source": "sample",
        "warnings": [],
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
                    },
                    "extreme_target": {
                        "decision": "review",
                        "reason": "promising_but_unstable",
                        "selected_model": {"feature": "roc_4w", "threshold": -0.04},
                        "metrics": {"split_f1": 0.16, "walk_forward_f1": 0.02},
                    },
                },
            },
            "CL=F": {
                "family": "commodity_shock",
                "adverse_direction": "higher",
                "targets": {
                    "warning_target": {
                        "decision": "reject",
                        "reason": "insufficient_out_of_sample",
                        "selected_model": {"feature": "level_and_roc_4w", "threshold": 0.68},
                        "metrics": {"split_f1": 0.15, "walk_forward_f1": 0.22},
                    }
                },
            },
        },
    }

    registry = build_risk_line_model_registry(selection)

    assert registry["live_indicator_count"] == 1
    assert registry["stage_coverage"]["warning_target"] == 1
    assert registry["stage_coverage"]["extreme_target"] == 0
    assert registry["live_models"]["SPY"]["targets"]["warning_target"]["selected_model"]["feature"] == "level_zscore"
    assert registry["review_queue"]["SPY"]["targets"]["extreme_target"]["decision"] == "review"
    assert registry["rejected_targets"]["CL=F"]["targets"]["warning_target"]["decision"] == "reject"
