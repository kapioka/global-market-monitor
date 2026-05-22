from __future__ import annotations

from datetime import date

from project.fx_soft_cap_watchlist import build_fx_soft_cap_watchlist, render_fx_soft_cap_watchlist_markdown


def test_fx_soft_cap_watchlist_tracks_waiting_future_data():
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
    payload = build_fx_soft_cap_watchlist(history, [], {"spot_score_watch": 0.45, "spot_score_buy": 0.65}, today=date(2026, 5, 21))

    assert payload["tracked_case_count"] == 1
    assert payload["waiting_future_data_count"] == 1
    assert payload["cases"][0]["review_status"] == "waiting_4w"
    assert payload["cases"][0]["next_review_date"] == "2026-06-04"
    assert payload["cases"][0]["detected_regime"] == "fx_stress"
    assert "regime_aware_fx_policy" in payload
    assert "waiting future data: 1" in render_fx_soft_cap_watchlist_markdown(payload)


def test_fx_soft_cap_watchlist_marks_ready_when_26w_available():
    history = [
        {
            "generated_at": "2026-01-01T07:30:00",
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
        {"date": "2026-01-01T00:00:00", "price": 100.0},
        {"date": "2026-07-03T00:00:00", "price": 110.0},
    ]
    payload = build_fx_soft_cap_watchlist(history, prices, {"spot_score_watch": 0.45, "spot_score_buy": 0.65}, today=date(2026, 8, 1))

    assert payload["ready_for_review_count"] == 1
    assert payload["cases"][0]["review_status"] == "ready_for_review"

