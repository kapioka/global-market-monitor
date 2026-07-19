from __future__ import annotations

from project.risk_engine_v2_promotion_gate import PromotionGateCriteria, evaluate_risk_engine_v2_promotion_gate


def test_promotion_gate_blocks_without_strict_primary_replay():
    replay = {
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "summary": {
            "total_cases": 34,
            "strict_primary_available": False,
            "primary_strict_available_cases": 0,
        },
    }
    review = {
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "case_count": 34,
        "episode_count": 12,
        "counts": {"insufficient_outcome": 1},
    }

    gate = evaluate_risk_engine_v2_promotion_gate(replay, review)

    assert gate["promotion_allowed"] is False
    assert gate["status"] == "blocked"
    assert "strict primary official-series replay is unavailable" in gate["blockers"]
    assert "holdout validation has not been run" in gate["blockers"]
    assert gate["warnings"] == ["episodes with insufficient outcome evidence: 1"]


def test_promotion_gate_still_requires_manual_approval_when_evidence_is_large():
    replay = {
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "summary": {
            "total_cases": 120,
            "strict_primary_available": True,
            "primary_strict_available_cases": 100,
        },
    }
    review = {
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "case_count": 120,
        "episode_count": 40,
        "counts": {"insufficient_outcome": 0},
    }

    gate = evaluate_risk_engine_v2_promotion_gate(replay, review)

    assert gate["promotion_allowed"] is False
    assert gate["blockers"] == ["holdout validation has not been run"]


def test_promotion_gate_criteria_are_configurable_for_review_diagnostics():
    replay = {
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "summary": {
            "total_cases": 10,
            "strict_primary_available": True,
            "primary_strict_available_cases": 10,
        },
    }
    review = {
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "case_count": 10,
        "episode_count": 5,
        "counts": {"insufficient_outcome": 0},
    }

    gate = evaluate_risk_engine_v2_promotion_gate(
        replay,
        review,
        holdout_payload={
            "policy_status": "diagnostic_only_not_promoted",
            "affects_final_action": False,
            "decision": {"promotion_allowed": False},
            "holdout": {"status": "accepted"},
        },
        criteria=PromotionGateCriteria(minimum_total_cases=10, minimum_primary_strict_cases=10, minimum_episode_count=5),
    )

    assert gate["criteria"]["minimum_total_cases"] == 10
    assert gate["observed"]["holdout_status"] == "accepted"
    assert gate["blockers"] == ["manual approval is required before promotion"]
