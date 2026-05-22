from __future__ import annotations

from project.fx_risk_policy import apply_fx_policy_candidate, classify_fx_policy


def test_classify_fx_policy_soft_cap_for_headwind():
    result = classify_fx_policy(
        {"level": "moderate", "flags": ["foreign_asset_fx_headwind"]},
        {"flags": ["japan_fx_risk_moderate"]},
    )

    assert result["fx_policy_classification"] == "soft_cap"
    assert result["fx_action_cap"] == "buy_candidate"
    assert result["affects_final_action"] is True


def test_apply_fx_soft_cap_keeps_candidate_but_caps_buy_window():
    classification = {"fx_policy_classification": "soft_cap", "flags": ["foreign_asset_fx_headwind"], "fx_execution_note": "note"}

    assert apply_fx_policy_candidate("buy_window", classification, "fx_soft_cap")["final_action"] == "buy_candidate"
    assert apply_fx_policy_candidate("buy_candidate", classification, "fx_soft_cap")["final_action"] == "buy_candidate"
    assert apply_fx_policy_candidate("buy_window", classification, "fx_note_only")["final_action"] == "buy_window"
