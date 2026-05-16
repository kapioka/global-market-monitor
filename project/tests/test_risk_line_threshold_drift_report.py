from __future__ import annotations

from project.risk_line_threshold_drift_report import render_risk_line_threshold_drift_markdown


def test_render_risk_line_threshold_drift_markdown():
    text = render_risk_line_threshold_drift_markdown(
        {
            "active_version": "v1",
            "generated_at": "2026-04-05T12:00:00+09:00",
            "summary": {
                "stable_count": 1,
                "watch_count": 1,
                "review_count": 1,
                "unavailable_count": 0,
                "review_targets": ["^VIX:danger"],
                "watch_targets": ["SPY:warning"],
            },
            "drift_rows": [
                {
                    "ticker": "SPY",
                    "stage": "warning",
                    "feature": "drawdown_13w",
                    "threshold": -0.02,
                    "direction": "lower",
                    "recent_hit_rate_26w": 0.1,
                    "history_hit_rate": 0.12,
                    "drift_gap": -0.02,
                    "drift_status": "stable",
                    "current_line_level": "normal",
                }
            ],
        }
    )
    assert "# Risk Line Threshold Drift" in text
    assert "summary: stable=1 / watch=1 / review=1 / unavailable=0" in text
    assert "review_targets: ^VIX:danger" in text
    assert "SPY / warning" in text
