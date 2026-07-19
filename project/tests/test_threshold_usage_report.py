from project.report_generator import render_developer_diagnostics_markdown, render_html, render_markdown
from project.tests.test_report_generator import _report
from project.threshold_certainty import build_threshold_certainty
from project.threshold_decision_policy import build_threshold_usage


def test_threshold_usage_report_shape():
    certainty = build_threshold_certainty(
        active_summary={"action_counts": {"wait": 1}},
        proposed_summary={"action_counts": {"wait": 1}},
        candidate_summary={"action_counts": {"wait": 1}},
        metadata_summary={"counts": {"fallback_review": 1}},
    )
    usage = build_threshold_usage(certainty, {"counts": {"fallback_review": 1}})

    assert "active" in certainty
    assert usage["operational_set"] == "active"
    assert usage["proposed_status"] == "hold"


def test_threshold_usage_section_appears_only_in_developer_diagnostics():
    report = _report()
    report["threshold_usage"] = {
        "operational_set": "active",
        "proposed_status": "hold",
        "candidate_v2_status": "diagnostic_only",
        "affects_final_action": False,
        "currently_affects_final_action": False,
    }
    report["threshold_certainty"] = {
        "active": {"level": "low"},
        "proposed": {"level": "not_evaluable"},
        "candidate_v2": {"level": "not_evaluable"},
    }
    report["threshold_rule_certification"] = {
        "summary": {
            "certified_count": 0,
            "conditional_count": 0,
            "diagnostic_only_count": 1,
            "hold_count": 0,
            "reject_count": 0,
            "not_evaluable_count": 1,
        },
        "currently_affects_final_action": False,
    }

    markdown = render_markdown(report)
    developer_markdown = render_developer_diagnostics_markdown(report)
    html = render_html(report)

    assert "しきい値利用方針" not in markdown
    assert "しきい値利用方針" in developer_markdown
    assert "実運用しきい値: 実運用" in developer_markdown
    assert "提案中しきい値: 保留" in developer_markdown
    assert "候補版v2: 診断専用" in developer_markdown
    assert "最終判断の根拠: 実運用しきい値 + データ信頼性方針" in developer_markdown
    assert "提案中しきい値 / 候補版v2 の最終判断への影響: いいえ" in developer_markdown
    assert "しきい値利用方針" not in html
    assert "実運用しきい値 + データ信頼性方針" not in html


def test_threshold_usage_section_handles_missing_payload():
    report = _report()
    report.pop("threshold_usage", None)
    report.pop("threshold_certainty", None)

    markdown = render_markdown(report)
    developer_markdown = render_developer_diagnostics_markdown(report)
    html = render_html(report)

    assert "しきい値利用方針" not in markdown
    assert "しきい値利用方針" in developer_markdown
    assert "実運用しきい値: -" in developer_markdown
    assert "しきい値利用方針" not in html
