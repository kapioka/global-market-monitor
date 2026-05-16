from __future__ import annotations

from project.decision_attribution import build_decision_attribution


def test_decision_attribution_includes_recovery_blocker_risk_and_reliability_cap():
    result = build_decision_attribution(
        spot_signal={
            "recovery_evidence": {"grade": "confirmed", "score": 0.82},
            "blocker_assessment": {"level": "caution"},
            "action_decision": {
                "reliability_cap_applied": True,
                "cap_reason": ["sample_fallback_present"],
            },
        },
        risk_lines={"stage_key": "credit_spillover_initial", "penalty_hint": 0.08},
        reliability={"reason_code": "sample_fallback_present"},
    )

    assert {entry["source"] for entry in result} == {
        "recovery_evidence",
        "blocker_assessment",
        "risk_lines",
        "reliability_policy",
    }
    assert result[-1]["effect"] == "cap"
    assert result[-1]["reason"] == "sample_fallback_present"


def test_decision_attribution_can_be_empty_for_neutral_wait():
    result = build_decision_attribution(
        spot_signal={
            "recovery_evidence": {"grade": "weak", "score": 0.2},
            "blocker_assessment": {"level": "none"},
            "action_decision": {"reliability_cap_applied": False},
        },
        risk_lines={"stage_key": "normal"},
        reliability={},
    )

    assert result == []
