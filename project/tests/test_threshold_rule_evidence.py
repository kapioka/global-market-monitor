from project.threshold_rule_evidence import build_rule_evidence


def test_rule_evidence_marks_inconclusive_changed_case_for_oil_rule():
    identities = [
        {
            "rule_id": "BZ=F:danger",
            "indicator": "BZ=F",
            "family": "commodity_oil",
            "threshold_type": "danger",
            "source": "fallback_review",
            "confidence": "fallback_review",
        },
        {
            "rule_id": "CL=F:extreme",
            "indicator": "CL=F",
            "family": "commodity_oil",
            "threshold_type": "extreme",
            "source": "fallback_review",
            "confidence": "fallback_review",
        },
    ]
    changed_cases = {
        "cases": [
            {
                "active": {"final_action": "watch", "risk_stage": "normal"},
                "proposed": {"final_action": "wait", "risk_stage": "extreme_danger_line_reached"},
                "classification": "inconclusive",
                "contributing_indicators": [
                    {"ticker": "BZ=F", "proposed_level": "danger"},
                    {"ticker": "CL=F", "proposed_level": "extreme"},
                ],
                "forward_returns": {"4w": None},
                "max_drawdowns": {"4w": None},
            }
        ]
    }

    evidence = build_rule_evidence(identities, changed_cases, {"action_summary": {"buy_window": {"count": 0}}})
    rows = {row["rule_id"]: row for row in evidence["rules"]}

    assert rows["BZ=F:danger"]["watch_to_wait_count"] == 1
    assert rows["BZ=F:danger"]["normal_to_extreme_count"] == 1
    assert rows["BZ=F:danger"]["family_overlap_count"] == 1
    assert rows["BZ=F:danger"]["inconclusive_count"] == 1
    assert rows["BZ=F:danger"]["buy_window_count"] == 0
