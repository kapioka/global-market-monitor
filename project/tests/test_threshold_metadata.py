from project.threshold_metadata import metadata_for_payload, rule_metadata, threshold_family


def test_threshold_family_maps_oil_tickers():
    assert threshold_family("CL=F") == "commodity_oil"
    assert threshold_family("BZ=F") == "commodity_oil"


def test_fallback_review_is_diagnostic_only():
    metadata = rule_metadata(
        "BZ=F",
        "extreme",
        {"threshold": 0.1, "decision": "fallback_review", "selection_mode": "fallback_review", "coverage_forced": True},
    )

    assert metadata["source"] == "fallback_review"
    assert metadata["confidence"] == "fallback_review"
    assert metadata["allow_final_action"] is False
    assert metadata["allow_extreme_stage"] is False


def test_unknown_metadata_is_not_evaluable():
    metadata = rule_metadata("UNKNOWN", "warning", {})

    assert metadata["family"] == "unknown"
    assert metadata["confidence"] == "not_evaluable"
    assert metadata["allow_final_action"] is False


def test_metadata_for_payload_counts_rules():
    payload = {
        "threshold_set": {"generated_at": "2026-05-15T00:00:00+09:00"},
        "indicators": {"SPY": {"thresholds": {"warning": {"threshold": -0.02, "decision": "adopt"}}}},
    }

    result = metadata_for_payload(payload)

    assert result["counts"]["total_rules"] == 1
    assert result["rules"][0]["indicator"] == "SPY"
