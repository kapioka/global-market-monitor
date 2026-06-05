from __future__ import annotations

from project.decision_boundary_experiment import build_decision_boundary_experiment


def _report(level: str = "caution") -> dict:
    return {
        "buy_decision_card": {
            "final_action": "watch",
            "buy_readiness_score": 31,
        },
        "japan_resident_integrated_risk_context": {
            "combined_context_level": level,
            "source_sections": ["risk_lines", "domestic_danger_context"],
        },
    }


def test_decision_boundary_experiment_keeps_production_defaults_disabled() -> None:
    payload = build_decision_boundary_experiment(_report())

    assert payload["enabled"] is False
    assert payload["must_not_affect_production_default"] is True
    assert payload["baseline"]["final_action"] == "watch"
    assert payload["experimental"]["final_action"] == "watch"
    assert payload["diff"]["action_changed"] is False


def test_decision_boundary_experiment_compares_adjusted_score_without_mutating_baseline() -> None:
    report = _report("caution")
    payload = build_decision_boundary_experiment(report)

    assert report["buy_decision_card"]["buy_readiness_score"] == 31
    assert payload["baseline"]["buy_readiness_score"] == 31
    assert payload["experimental"]["adjusted_buy_readiness_score"] == 23
    assert payload["diff"]["score_delta"] == -8
    assert payload["experimental"]["supplemental_warning_level"] == "caution"


def test_decision_boundary_experiment_stronger_context_gets_larger_discount() -> None:
    watch = build_decision_boundary_experiment(_report("watch"))
    block = build_decision_boundary_experiment(_report("block"))

    assert watch["diff"]["score_delta"] == -4
    assert block["diff"]["score_delta"] == -12
    assert block["experimental"]["adjusted_buy_readiness_score"] == 19


def test_decision_boundary_experiment_normal_context_has_no_adjustment() -> None:
    payload = build_decision_boundary_experiment(_report("normal"))

    assert payload["diff"]["score_delta"] == 0
    assert payload["experimental"]["adjusted_buy_readiness_score"] == 31
    assert payload["experimental"]["suggested_adjustment"] == "no_experimental_score_adjustment"
