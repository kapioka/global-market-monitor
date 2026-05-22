from __future__ import annotations

from project.buy_window_diagnostics import build_buy_window_diagnostics, render_buy_window_diagnostics_markdown


def test_buy_window_diagnostics_handles_zero_buy_window():
    payload = build_buy_window_diagnostics(
        [
            {
                "generated_at": "2026-01-02T07:30:00",
                "score": {"total_score": 0.51},
                "data_reliability": {"level": "medium", "max_action": "watch"},
                "risk_lines": {"stage_key": "danger_line_reached", "decision_level": "block"},
                "spot_signal": {
                    "action_layers": {
                        "market_raw_action": "watch",
                        "risk_adjusted_action": "wait",
                        "final_action": "wait",
                    },
                    "action_decision": {"reliability_cap_applied": True},
                    "recovery_evidence": {"grade": "weak"},
                    "blocker_assessment": {"level": "block", "flags": ["credit_stress_severe"]},
                },
                "regime": {"credit_regime_flag": "credit_stress_severe"},
            }
        ]
    )

    assert payload["status"] == "ok"
    assert payload["final_buy_window_count"] == 0
    assert payload["blocker_counts"]["risk_line_block"] == 1
    assert payload["blocker_counts"]["reliability_policy_cap"] == 1
    assert payload["buy_window_zero_reason_summary"]
    assert "raw buy_window: 0" in render_buy_window_diagnostics_markdown(payload)


def test_buy_window_diagnostics_separates_raw_and_final():
    payload = build_buy_window_diagnostics(
        [
            {
                "generated_at": "2026-01-02T07:30:00",
                "data_reliability": {"level": "medium", "max_action": "watch"},
                "risk_lines": {"stage_key": "normal", "decision_level": "none"},
                "spot_signal": {
                    "action_layers": {
                        "market_raw_action": "buy_window",
                        "risk_adjusted_action": "buy_window",
                        "final_action": "watch",
                    },
                    "action_decision": {"reliability_cap_applied": True},
                    "recovery_evidence": {"grade": "confirmed"},
                    "blocker_assessment": {"level": "none", "flags": []},
                },
            }
        ]
    )

    assert payload["raw_buy_window_count"] == 1
    assert payload["raw_buy_window_to_watch_count"] == 1
    assert payload["final_buy_window_count"] == 0


def test_buy_window_diagnostics_includes_buy_candidate_performance():
    payload = build_buy_window_diagnostics(
        [
            {
                "generated_at": "2026-01-02T07:30:00",
                "spot_signal": {
                    "action_layers": {
                        "market_raw_action": "buy_candidate",
                        "risk_adjusted_action": "buy_candidate",
                        "final_action": "buy_candidate",
                    },
                    "recovery_evidence": {"grade": "building"},
                    "blocker_assessment": {"level": "none", "flags": []},
                },
            },
            {
                "generated_at": "2026-01-09T07:30:00",
                "spot_signal": {
                    "action_layers": {
                        "market_raw_action": "buy_window",
                        "risk_adjusted_action": "buy_window",
                        "final_action": "buy_window",
                    },
                    "recovery_evidence": {"grade": "confirmed"},
                    "blocker_assessment": {"level": "none", "flags": []},
                },
            },
        ],
        {
            "action_summary": {
                "buy_candidate": {
                    "count": 1,
                    "horizons": {"13w": {"mean_return": 0.03, "mean_excess_return": 0.01, "worst_max_drawdown": -0.02}},
                }
            }
        },
    )

    assert payload["raw_buy_candidate_count"] == 1
    assert payload["risk_adjusted_buy_candidate_count"] == 1
    assert payload["final_buy_candidate_count"] == 1
    assert payload["buy_candidate_to_buy_window_transition_count"] == 1
    assert payload["buy_candidate_performance"]["count"] == 1
