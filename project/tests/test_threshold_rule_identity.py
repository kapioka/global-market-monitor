from project.threshold_rule_identity import build_rule_id, build_rule_identity, identities_from_payloads, split_rule_id


def test_rule_id_is_stable_for_ticker_with_colon_free_threshold_type():
    assert build_rule_id("^VIX", "warning") == "^VIX:warning"
    assert split_rule_id("HYG/LQD:danger") == ("HYG/LQD", "danger")


def test_identity_handles_active_rule_without_metadata():
    identity = build_rule_identity("^VIX", "warning", active_rule={"threshold": 25.0})

    assert identity["rule_id"] == "^VIX:warning"
    assert identity["family"] == "volatility"
    assert identity["active_value"] == 25.0


def test_identities_match_active_and_proposed_rules():
    active = {"indicators": {"^VIX": {"thresholds": {"warning": {"threshold": 25.0}}}}}
    proposed = {"indicators": {"^VIX": {"thresholds": {"warning": {"threshold": 22.0}}}}}

    rows = identities_from_payloads(active_payload=active, proposed_payload=proposed)

    assert rows[0]["rule_id"] == "^VIX:warning"
    assert rows[0]["active_value"] == 25.0
    assert rows[0]["proposed_value"] == 22.0
