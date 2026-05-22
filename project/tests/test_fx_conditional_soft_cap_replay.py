from __future__ import annotations

from project.fx_conditional_soft_cap_replay import build_fx_conditional_soft_cap_replay, render_fx_conditional_soft_cap_replay_markdown


def test_conditional_replay_compares_candidates() -> None:
    replay = {
        "cases": [
            {
                "classification": "overblocked_by_current",
                "risk_stage": "normal",
                "reliability_level": "historical_price_replay",
                "market_raw_action": "buy_candidate",
                "current_final_action": "watch",
                "score_band": "strong",
                "fx_flags": ["japan_fx_risk_caution"],
                "feature_snapshot": {"hyg_lqd_ratio_return_4w": 0.01, "vix_level": 18.0, "usdjpy_change_4w": -0.03},
                "forward_returns": {"13w": 0.05},
                "excess_returns": {"13w": 0.01},
                "max_drawdowns": {"13w": -0.03},
            },
            {
                "classification": "correctly_blocked",
                "risk_stage": "normal",
                "reliability_level": "historical_price_replay",
                "market_raw_action": "buy_candidate",
                "current_final_action": "watch",
                "score_band": "strong",
                "fx_flags": ["japan_fx_risk_caution"],
                "feature_snapshot": {"hyg_lqd_ratio_return_4w": -0.05, "vix_level": 35.0, "usdjpy_change_4w": -0.03},
                "forward_returns": {"13w": -0.05},
                "excess_returns": {"13w": -0.03},
                "max_drawdowns": {"13w": -0.12},
            },
        ]
    }

    payload = build_fx_conditional_soft_cap_replay(replay)
    combined = next(row for row in payload["candidates"] if row["candidate"] == "combined_conservative")

    assert combined["buy_candidate_count"] == 1
    assert combined["correctly_blocked_count"] == 0
    assert payload["affects_final_action"] is False
    assert "conditional fx_soft_cap" in render_fx_conditional_soft_cap_replay_markdown(payload)
