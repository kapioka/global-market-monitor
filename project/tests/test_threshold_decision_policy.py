from project.threshold_decision_policy import build_threshold_usage


def test_uncertified_candidate_does_not_affect_final_action():
    certainty = {
        "proposed": {"level": "not_evaluable", "blocking_reasons": ["buy_window_count_is_zero"]},
        "candidate_v2": {"level": "not_evaluable", "blocking_reasons": ["all_cases_are_wait"]},
    }

    usage = build_threshold_usage(certainty, {"counts": {"fallback_review": 22}})

    assert usage["operational_set"] == "active"
    assert usage["candidate_v2_status"] == "diagnostic_only"
    assert usage["affects_final_action"] is False
