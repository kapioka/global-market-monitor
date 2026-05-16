from project.report_generator import render_html, render_markdown
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


def test_threshold_usage_section_appears_in_markdown_and_html():
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
    html = render_html(report)

    assert "Threshold Usage" in markdown
    assert "実運用閾値: active" in markdown
    assert "proposed threshold: hold" in markdown
    assert "candidate_v2: diagnostic_only" in markdown
    assert "final action source: active threshold + reliability policy" in markdown
    assert "proposed / candidate_v2 affects final action: False" in markdown
    assert "Threshold Usage" in html
    assert "active threshold + reliability policy" in html


def test_threshold_usage_section_handles_missing_payload():
    report = _report()
    report.pop("threshold_usage", None)
    report.pop("threshold_certainty", None)

    markdown = render_markdown(report)
    html = render_html(report)

    assert "Threshold Usage" in markdown
    assert "実運用閾値: -" in markdown
    assert "Threshold Usage" in html
