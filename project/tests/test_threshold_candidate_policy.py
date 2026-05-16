from project.threshold_candidate_policy import allows_extreme, apply_candidate_v2_policy, family_severity


def test_oil_family_counts_once():
    result = family_severity(
        [
            {"ticker": "CL=F", "line_level": "extreme"},
            {"ticker": "BZ=F", "line_level": "extreme"},
        ]
    )

    assert result["commodity_oil"]["extreme"] == 1


def test_oil_only_does_not_allow_extreme():
    levels = family_severity([{"ticker": "CL=F", "line_level": "extreme"}, {"ticker": "BZ=F", "line_level": "extreme"}])

    assert allows_extreme(levels, {"composite_risk_score": 50}, previous_stage="normal") is False


def test_volatility_and_credit_can_allow_extreme():
    levels = family_severity([{"ticker": "^VIX", "line_level": "extreme"}, {"ticker": "HYG/LQD", "line_level": "danger"}])

    assert allows_extreme(levels, {"composite_risk_score": 70}, previous_stage="caution") is True


def test_normal_to_extreme_limiter_downgrades():
    risk_lines = {
        "stage_key": "extreme_danger_line_reached",
        "stage_label": "非常に危険ライン到達",
        "penalty_hint": 0.14,
        "composite_risk_score": 42,
        "indicators": [{"ticker": "BZ=F", "line_level": "extreme"}],
    }

    result = apply_candidate_v2_policy(risk_lines, previous_stage="normal")

    assert result["stage_key"] == "danger_line_reached"
    assert result["candidate_v2"]["diagnostic_only"] is True
