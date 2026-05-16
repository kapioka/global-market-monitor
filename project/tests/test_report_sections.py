from __future__ import annotations

from project.report_sections.data_quality_section import data_quality_html_rows, data_quality_markdown_lines


def _report() -> dict:
    return {
        "data_reliability": {
            "level": "medium",
            "live_ratio": 0.75,
            "max_action": "watch",
            "confidence_cap": 0.45,
            "proxy_fallback_count": 1,
            "sample_fallback_count": 0,
            "unavailable_count": 1,
            "critical_failures": ["ACWI"],
            "reason_code": "critical_series_unavailable",
        },
        "spot_signal": {
            "action_decision": {
                "reliability_cap_applied": True,
                "cap_reason": ["critical_series_unavailable"],
            }
        },
    }


def test_data_quality_markdown_lines_summarize_policy():
    lines = data_quality_markdown_lines(_report())

    assert "- live 取得率: 75%" in lines
    assert any("データ品質上限: 監視" in line for line in lines)
    assert any("critical_series_unavailable" in line for line in lines)


def test_data_quality_html_rows_summarize_policy():
    rows = dict(data_quality_html_rows(_report()))

    assert rows["判定信頼性"] == "中"
    assert rows["live 取得率"] == "75%"
    assert "ACWI" in rows["重要系列不足"]
