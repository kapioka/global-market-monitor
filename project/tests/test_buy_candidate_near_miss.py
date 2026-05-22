from __future__ import annotations

from project.buy_candidate_near_miss import build_buy_candidate_near_miss, render_buy_candidate_near_miss_markdown


def test_buy_candidate_near_miss_finds_one_missing_condition():
    history = [
        {
            "generated_at": "2026-01-01T07:30:00",
            "data_reliability": {"level": "high", "max_action": "buy_window"},
            "risk_lines": {"stage_key": "normal"},
            "score": {"total_score": 0.6},
            "spot_signal": {
                "adjusted_score": 0.6,
                "action_decision": {"action": "watch"},
                "recovery_evidence": {"grade": "building", "score": 0.6},
                "blocker_assessment": {
                    "level": "caution",
                    "flags": ["japan_fx_risk_moderate", "foreign_asset_fx_headwind"],
                },
            },
        }
    ]

    payload = build_buy_candidate_near_miss(history, {"spot_score_watch": 0.45, "spot_score_buy": 0.65})

    assert payload["near_miss_count"] == 1
    assert payload["missing_condition_counts"]["japan_fx_risk_caution"] == 1
    assert payload["top_near_miss_cases"][0]["score_gap_to_candidate"] == 0.0
    assert "near_miss_count: 1" in render_buy_candidate_near_miss_markdown(payload)


def test_buy_candidate_near_miss_handles_zero_cases():
    payload = build_buy_candidate_near_miss([], {"spot_score_watch": 0.45, "spot_score_buy": 0.65})

    assert payload["near_miss_count"] == 0
    assert "near-miss cases were not found" in render_buy_candidate_near_miss_markdown(payload)
