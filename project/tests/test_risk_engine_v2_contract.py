from __future__ import annotations

import pytest

from project.risk_engine_v2_contract import attach_shadow_diagnostic_contract


def test_shadow_diagnostic_contract_attaches_pass_metadata():
    payload = {
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "replay_type": "risk_engine_v2_shadow",
        "decision": {"promotion_allowed": False},
    }

    result = attach_shadow_diagnostic_contract(payload, artifact_type="replay")

    assert result["contract"]["status"] == "pass"
    assert result["contract"]["promotion_allowed"] is False
    assert "contract" not in payload


def test_shadow_diagnostic_contract_rejects_promotion():
    payload = {
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "replay_type": "risk_engine_v2_shadow",
        "decision": {"promotion_allowed": True},
    }

    with pytest.raises(ValueError, match="promotion_allowed"):
        attach_shadow_diagnostic_contract(payload, artifact_type="replay")


def test_reconstructed_replay_contract_requires_history_unchanged():
    payload = {
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "replay_type": "risk_engine_v2_reconstructed_shadow",
        "decision": {"promotion_allowed": False},
        "reconstruction": {"history_files_modified": True},
    }

    with pytest.raises(ValueError, match="history"):
        attach_shadow_diagnostic_contract(payload, artifact_type="reconstructed_replay")
