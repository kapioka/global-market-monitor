from __future__ import annotations

from project.fx_soft_cap_outcome_analysis import build_fx_soft_cap_outcome_analysis, render_fx_soft_cap_outcome_analysis_markdown


def test_fx_soft_cap_outcome_analysis_groups_classifications() -> None:
    payload = {
        "cases": [
            {
                "classification": "overblocked_by_current",
                "risk_stage": "normal",
                "reliability_level": "historical_price_replay",
                "score_band": "strong",
                "fx_flags": ["japan_fx_risk_caution"],
                "excess_returns": {"13w": 0.02},
                "max_drawdowns": {"13w": -0.03},
                "feature_snapshot": {"vix_level": 18.0, "usdjpy_change_4w": -0.02},
            },
            {
                "classification": "correctly_blocked",
                "risk_stage": "normal",
                "reliability_level": "historical_price_replay",
                "score_band": "candidate",
                "fx_flags": ["foreign_asset_fx_headwind"],
                "excess_returns": {"13w": -0.04},
                "max_drawdowns": {"13w": -0.1},
                "feature_snapshot": {"vix_level": 29.0, "usdjpy_change_4w": -0.05},
            },
        ]
    }

    result = build_fx_soft_cap_outcome_analysis(payload)

    assert result["classification_counts"]["overblocked_by_current"] == 1
    assert result["by_classification"]["correctly_blocked"]["feature_medians"]["vix_level"] == 29.0
    assert "outcome analysis" in render_fx_soft_cap_outcome_analysis_markdown(result)
