from project.threshold_rule_certification import certify_rule, certify_threshold_rules


def test_fallback_review_rule_is_not_certified():
    row = certify_rule(
        {
            "rule_id": "BZ=F:danger",
            "indicator": "BZ=F",
            "family": "commodity_oil",
            "threshold_type": "danger",
            "source": "fallback_review",
            "confidence": "fallback_review",
            "trigger_count": 1,
            "buy_window_count": 0,
            "watch_to_wait_count": 1,
            "normal_to_extreme_count": 1,
            "family_overlap_count": 1,
            "completed_13w_count": 0,
            "completed_26w_count": 0,
            "inconclusive_count": 1,
        }
    )

    assert row["certification_status"] in {"diagnostic_only", "reject", "not_evaluable"}
    assert "final_action" not in row["allowed_usage"]
    assert row["currently_affects_final_action"] is False


def test_buy_window_zero_prevents_certification():
    row = certify_rule(
        {
            "rule_id": "^VIX:warning",
            "indicator": "^VIX",
            "family": "volatility",
            "threshold_type": "warning",
            "source": "historical_quantile",
            "confidence": "high",
            "trigger_count": 4,
            "buy_window_count": 0,
            "completed_13w_count": 4,
            "completed_26w_count": 2,
            "beneficial_block_count": 2,
            "overblocked_count": 0,
            "normal_to_extreme_count": 0,
            "watch_to_wait_count": 0,
            "family_overlap_count": 0,
            "inconclusive_count": 0,
        }
    )

    assert row["certification_status"] != "certified"
    assert "buy_window_count_is_zero" in row["blocking_reasons"]


def test_summary_handles_zero_certified_rules():
    payload = certify_threshold_rules({"rules": []})

    assert payload["summary"]["certified_count"] == 0
    assert payload["currently_affects_final_action"] is False
