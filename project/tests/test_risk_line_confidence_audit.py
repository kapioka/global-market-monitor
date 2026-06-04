from __future__ import annotations

from project.risk_line_confidence_audit import build_risk_line_confidence_audit


def test_risk_line_confidence_audit_summarizes_threshold_confidence_without_decision_effect() -> None:
    payload = {
        "threshold_set": {"generated_at": "2026-04-05T12:00:00+09:00"},
        "indicators": {
            "DX-Y.NYB": {
                "thresholds": {
                    "warning": {"feature": "level_percentile", "threshold": 0.78},
                    "extreme": {
                        "feature": "roc_z_1w",
                        "threshold": 1.14,
                        "decision": "fallback_review",
                        "selection_mode": "fallback_review",
                        "coverage_forced": True,
                    },
                }
            },
            "^VIX": {
                "thresholds": {
                    "danger": {
                        "feature": "level",
                        "threshold": 30,
                        "decision": "adopt",
                        "actual_value_check": {"status": "pass"},
                        "backtest_metrics": {"precision": 0.52},
                    },
                    "warning": {
                        "feature": "level",
                        "threshold": 25,
                        "decision": "adopt",
                        "actual_value_check": {"status": "review"},
                        "backtest_metrics": {"precision": 0.2},
                    },
                }
            },
        },
    }
    risk_lines = {
        "composite_risk_score": 48.2,
        "trigger_path": [{"type": "indicator", "indicator": "^VIX"}, {"type": "composite_score", "score": 48.2}],
    }

    audit = build_risk_line_confidence_audit(payload, risk_lines)

    assert audit["status"] == "display_only"
    assert audit["monitoring_scope"] == "us_global_risk_core"
    assert audit["fallback_review_rules"] == 1
    assert audit["low_precision_rules"] == 1
    assert audit["pass_rules"] == 1
    assert audit["dxy_role"]["separate_from"] == ["USDJPY=X", "EURJPY=X"]
    assert audit["jpy_fx_role"]["separate_from"] == "DX-Y.NYB"
    assert audit["must_not_affect_final_action"] is True
    assert audit["must_not_change_threshold_json"] is True
    assert "trigger path" in audit["composite_trigger_relationship"]
