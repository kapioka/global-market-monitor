from __future__ import annotations

from project.fx_soft_cap_missed_good_analysis import (
    build_fx_soft_cap_missed_good_analysis,
    render_fx_soft_cap_missed_good_analysis_markdown,
)


def test_missed_good_analysis_lists_excluded_overblocked_cases() -> None:
    replay = {
        "cases": [
            {
                "date": "2025-07-18",
                "classification": "overblocked_by_current",
                "fx_soft_cap_action": "buy_candidate",
                "current_final_action": "watch",
                "fx_flags": ["japan_fx_risk_caution"],
                "feature_snapshot": {
                    "acwi_spy_relative_13w": -0.02,
                    "vix_level": 16.0,
                    "vix_change_4w": 0.01,
                    "hyg_lqd_ratio_return_4w": 0.01,
                    "acwi_drawdown_13w": 0.0,
                    "acwi_return_4w": 0.03,
                    "acwi_return_13w": 0.1,
                },
                "forward_returns": {"13w": 0.05, "26w": 0.1},
                "excess_returns": {"13w": 0.01},
                "max_drawdowns": {"13w": -0.03},
            }
        ]
    }

    payload = build_fx_soft_cap_missed_good_analysis(replay)

    assert payload["missed_good_count"] == 1
    assert payload["cases"][0]["guard_reasons"] == ["equity_trend_ok"]
    assert "missed_good analysis" in render_fx_soft_cap_missed_good_analysis_markdown(payload)
