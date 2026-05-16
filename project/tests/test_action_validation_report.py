from __future__ import annotations

import json

from project.action_validation_report import render_action_validation_csv, render_action_validation_markdown, write_action_validation_report


def _payload() -> dict:
    return {
        "status": "ok",
        "action_summary": {
            "buy_window": {
                "count": 1,
                "reliability_capped_count": 0,
                "horizons": {
                    "4w": {"count": 1, "mean_return": 0.08, "median_return": 0.08, "win_rate": 1.0, "worst_max_drawdown": -0.02},
                    "13w": {"count": 1, "mean_return": 0.12, "median_return": 0.12, "win_rate": 1.0, "worst_max_drawdown": -0.03},
                    "26w": {"count": 1, "mean_return": 0.18, "median_return": 0.18, "win_rate": 1.0, "worst_max_drawdown": -0.04},
                    "52w": {"count": 0, "mean_return": None, "median_return": None, "win_rate": None, "worst_max_drawdown": None},
                },
            }
        },
        "diagnostics": {
            "buy_window_negative_rate_13w": 0.0,
            "wait_missed_rally_rate_13w": None,
            "watch_to_buy_window_promotion_rate": None,
        },
        "cases": [
            {
                "date": "2026-01-01",
                "action": "buy_window",
                "forward_returns": {"4w": 0.08, "13w": 0.12, "26w": 0.18, "52w": None},
                "max_drawdowns": {"4w": -0.02, "13w": -0.03, "26w": -0.04, "52w": None},
            }
        ],
    }


def test_render_action_validation_markdown_summarizes_payload():
    text = render_action_validation_markdown(_payload())

    assert "# action validation" in text
    assert "buy_window: count=1" in text
    assert "13w: count=1 / mean=12.00%" in text
    assert "buy_window_negative_rate_13w: 0.00%" in text
    assert "2026-01-01: buy_window" in text


def test_write_action_validation_report_writes_json_and_markdown(tmp_path):
    json_path, markdown_path = write_action_validation_report(_payload(), tmp_path)

    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == "ok"
    assert "action validation" in markdown_path.read_text(encoding="utf-8")
    assert json.loads((tmp_path / "action_validation_summary.json").read_text(encoding="utf-8"))["status"] == "ok"
    assert "buy_window,13w" in (tmp_path / "action_validation_summary.csv").read_text(encoding="utf-8")
    assert "action validation" in (tmp_path / "action_validation_summary.md").read_text(encoding="utf-8")


def test_render_action_validation_csv_outputs_summary_rows():
    text = render_action_validation_csv(_payload())

    assert "action,horizon,count" in text
    assert "buy_window,13w,1" in text
