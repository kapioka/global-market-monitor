from __future__ import annotations

from project.buy_window_calibration import build_buy_window_calibration, render_buy_window_calibration_markdown


def test_buy_window_calibration_does_not_auto_adopt_without_evidence():
    payload = build_buy_window_calibration(
        replay_diff={
            "summary": {
                "active_action_counts": {"wait": 10, "watch": 2, "buy_window": 0},
                "proposed_action_counts": {"wait": 9, "watch": 2, "buy_window": 1},
                "metrics": {"active": {}, "proposed": {}},
            }
        }
    )

    proposed = next(row for row in payload["candidates"] if row["label"] == "proposed_thresholds_review")
    assert proposed["decision"] == "hold"
    assert payload["policy"] == "calibration_only_no_active_threshold_change"
    assert "active/proposed threshold JSON" in render_buy_window_calibration_markdown(payload)
