from __future__ import annotations

from project.fx_soft_cap_dd_guard_replay import build_fx_soft_cap_dd_guard_replay, render_fx_soft_cap_dd_guard_replay_markdown


def test_dd_guard_replay_compares_guard_candidates() -> None:
    replay = {
        "return_summary": {"13w": {"worst_max_drawdown": -0.142534}},
        "cases": [
            {
                "classification": "correctly_blocked",
                "current_final_action": "watch",
                "fx_flags": ["foreign_asset_fx_headwind"],
                "feature_snapshot": {
                    "acwi_spy_relative_13w": -0.02,
                    "vix_level": 16.0,
                    "vix_change_4w": 0.02,
                    "hyg_lqd_ratio_return_4w": 0.0,
                    "acwi_drawdown_13w": -0.01,
                    "acwi_return_4w": 0.02,
                    "acwi_return_13w": 0.04,
                },
                "forward_returns": {"13w": -0.01},
                "excess_returns": {"13w": 0.01},
                "max_drawdowns": {"13w": -0.142534},
            },
            {
                "classification": "overblocked_by_current",
                "current_final_action": "watch",
                "fx_flags": ["japan_fx_risk_caution"],
                "feature_snapshot": {
                    "acwi_spy_relative_13w": 0.02,
                    "vix_level": 16.0,
                    "vix_change_4w": 0.02,
                    "hyg_lqd_ratio_return_4w": 0.01,
                    "acwi_drawdown_13w": 0.0,
                    "acwi_return_4w": 0.02,
                    "acwi_return_13w": 0.05,
                },
                "forward_returns": {"13w": 0.05},
                "excess_returns": {"13w": 0.02},
                "max_drawdowns": {"13w": -0.03},
            },
        ],
    }

    payload = build_fx_soft_cap_dd_guard_replay(replay)
    combined = next(row for row in payload["candidates"] if row["candidate"] == "combined_dd_guard")

    assert combined["buy_candidate_count"] == 1
    assert combined["excluded_deep_dd_count"] == 1
    assert payload["affects_final_action"] is False
    assert "DD guard replay" in render_fx_soft_cap_dd_guard_replay_markdown(payload)
