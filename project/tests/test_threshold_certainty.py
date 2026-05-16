from project.threshold_certainty import build_threshold_certainty


def test_proposed_with_zero_buy_window_is_not_high_certainty():
    result = build_threshold_certainty(
        active_summary={"action_counts": {"wait": 60, "watch": 7}},
        proposed_summary={"action_counts": {"wait": 67}, "cases_where_proposed_increased_wait": 7},
        candidate_summary={"action_counts": {"wait": 67}},
        metadata_summary={"counts": {"fallback_review": 22}},
    )

    assert result["proposed"]["level"] != "high"
    assert "buy_window_count_is_zero" in result["proposed"]["blocking_reasons"]
    assert "fallback_review_rules_present" in result["proposed"]["blocking_reasons"]
