from __future__ import annotations

from project.buy_window_case_study import build_buy_window_case_study, render_buy_window_case_study_markdown


def test_buy_window_case_study_handles_no_cases():
    payload = build_buy_window_case_study([], [])

    assert payload["status"] == "ok"
    assert payload["case_count"] == 0
    assert "降格されたケースはありません" in render_buy_window_case_study_markdown(payload)


def test_buy_window_case_study_classifies_overblocked_case():
    history = [
        {
            "generated_at": "2026-01-01T07:30:00",
            "data_reliability": {"level": "high", "max_action": "buy_window"},
            "risk_lines": {"stage_key": "normal", "trigger_path": [{"type": "indicator", "indicator": "^VIX"}]},
            "spot_signal": {
                "action_layers": {
                    "market_raw_action": "buy_window",
                    "risk_adjusted_action": "buy_window",
                    "final_action": "watch",
                    "layer_reasons": {"final_action": ["sample_fallback_present"]},
                },
                "action_decision": {"policy_reasons": ["sample_fallback_present"]},
                "recovery_evidence": {"grade": "confirmed", "score": 0.8},
                "blocker_assessment": {"level": "none", "primary_reasons": []},
            },
        }
    ]
    prices = [
        {"date": "2026-01-01T00:00:00", "price": 100.0},
        {"date": "2026-01-30T00:00:00", "price": 103.0},
        {"date": "2026-04-02T00:00:00", "price": 110.0},
        {"date": "2026-07-03T00:00:00", "price": 112.0},
    ]

    payload = build_buy_window_case_study(history, prices)

    assert payload["case_count"] == 1
    assert payload["cases"][0]["classification"] == "overblocked"
    assert payload["cases"][0]["risk_lines"]["trigger_path"]
