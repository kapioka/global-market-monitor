from __future__ import annotations

from project.fx_soft_cap_case_study import build_fx_soft_cap_case_study, render_fx_soft_cap_case_study_markdown


def test_fx_soft_cap_case_study_tracks_soft_cap_candidate():
    history = [
        {
            "generated_at": "2026-05-07T07:30:00",
            "japan_risk": {"level": "moderate", "flags": ["foreign_asset_fx_headwind"]},
            "data_reliability": {"level": "high"},
            "risk_lines": {"stage_key": "normal"},
            "score": {"total_score": 0.6},
            "spot_signal": {
                "legacy_action": "buy_window",
                "action": "watch",
                "adjusted_score": 0.6,
                "blocker_assessment": {"level": "caution", "flags": ["japan_fx_risk_moderate", "foreign_asset_fx_headwind"]},
                "recovery_evidence": {"grade": "building", "score": 0.6},
            },
        }
    ]
    prices = [
        {"date": "2026-05-07T00:00:00", "price": 100.0},
        {"date": "2026-06-05T00:00:00", "price": 101.0},
    ]

    payload = build_fx_soft_cap_case_study(history, prices, {"spot_score_watch": 0.45, "spot_score_buy": 0.65})

    assert payload["adoption_decision"] == "hold"
    assert payload["fx_soft_cap_buy_candidate_count"] == 1
    assert payload["cases"][0]["generated_at"] == "2026-05-07T07:30:00"
    assert payload["cases"][0]["fx_soft_cap_action"] == "buy_candidate"
    assert "diagnostic_only" in render_fx_soft_cap_case_study_markdown(payload)


def test_fx_soft_cap_case_study_tracks_convertible_near_miss_only():
    history = [
        {
            "generated_at": "2026-05-08T07:30:00",
            "data_reliability": {"level": "high", "max_action": "buy_window"},
            "risk_lines": {"stage_key": "normal"},
            "score": {"total_score": 0.6},
            "spot_signal": {
                "action": "watch",
                "adjusted_score": 0.6,
                "blocker_assessment": {"level": "caution", "flags": ["japan_fx_risk_moderate"]},
                "recovery_evidence": {"grade": "building", "score": 0.6},
            },
        },
        {
            "generated_at": "2026-05-09T07:30:00",
            "data_reliability": {"level": "high", "max_action": "buy_window"},
            "risk_lines": {"stage_key": "normal"},
            "score": {"total_score": 0.51},
            "spot_signal": {
                "action": "watch",
                "adjusted_score": 0.51,
                "blocker_assessment": {"level": "caution", "flags": ["japan_fx_risk_moderate"]},
                "recovery_evidence": {"grade": "building", "score": 0.6},
            },
        },
    ]

    payload = build_fx_soft_cap_case_study(history, [], {"spot_score_watch": 0.45, "spot_score_buy": 0.65})

    assert payload["fx_soft_cap_buy_candidate_count"] == 1
    assert payload["cases"][0]["generated_at"] == "2026-05-08T07:30:00"
