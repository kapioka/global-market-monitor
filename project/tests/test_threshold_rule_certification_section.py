from project.report_generator import render_html, render_markdown
from project.tests.test_report_generator import _report


def test_rule_certification_summary_appears_in_markdown_and_html():
    report = _report()
    report["threshold_rule_certification"] = {
        "summary": {
            "certified_count": 0,
            "conditional_count": 1,
            "diagnostic_only_count": 2,
            "hold_count": 3,
            "reject_count": 4,
            "not_evaluable_count": 5,
        },
        "top_blocking_reasons": [{"reason": "fallback_review", "count": 2}],
        "currently_affects_final_action": False,
    }

    markdown = render_markdown(report)
    html = render_html(report)

    assert "Threshold Rule Certification" in markdown
    assert "certified rules: 0" in markdown
    assert "Threshold Rule Certification" in html
    assert "fallback_review" in html
