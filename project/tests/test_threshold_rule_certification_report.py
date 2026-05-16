from project.threshold_rule_certification_report import render_threshold_rule_certification_markdown


def test_threshold_rule_certification_markdown_renders_empty_certified_count():
    markdown = render_threshold_rule_certification_markdown(
        {
            "summary": {
                "certified_count": 0,
                "conditional_count": 0,
                "diagnostic_only_count": 1,
                "hold_count": 0,
                "reject_count": 0,
                "not_evaluable_count": 1,
            },
            "currently_affects_final_action": False,
            "rules": [
                {
                    "rule_id": "BZ=F:danger",
                    "family": "commodity_oil",
                    "source": "fallback_review",
                    "confidence": "fallback_review",
                    "certification_status": "diagnostic_only",
                    "allowed_usage": ["diagnostic_report"],
                    "blocking_reasons": ["fallback_review"],
                }
            ],
        }
    )

    assert "certified rules: 0" in markdown
    assert "BZ=F:danger" in markdown
