from __future__ import annotations

from project.buy_blocker_breakdown import build_buy_blocker_breakdown
from project.buy_readiness_score import build_buy_readiness_score


def _watch_with_caution_blockers() -> dict:
    return {
        "spot_signal": {
            "action_layers": {"market_raw_action": "watch", "risk_adjusted_action": "watch", "final_action": "watch"},
            "recovery_evidence": {"grade": "building"},
            "blocker_assessment": {
                "level": "caution",
                "flags": ["rates_warning", "japan_fx_risk_moderate", "foreign_asset_fx_dependency"],
            },
        },
        "risk_lines": {"stage_key": "normal"},
        "data_reliability": {"level": "high", "decision_allowed": True},
        "score": {"total_score": 0.5789},
        "config": {"thresholds": {"spot_score_buy": 0.65}},
    }


def test_buy_readiness_score_is_bounded_and_explanatory() -> None:
    report = {
        "spot_signal": {
            "action_layers": {"market_raw_action": "buy_window", "risk_adjusted_action": "watch", "final_action": "watch"},
            "recovery_evidence": {"grade": "confirmed"},
            "blocker_assessment": {"flags": ["foreign_asset_fx_headwind"]},
        },
        "risk_lines": {"stage_key": "normal"},
        "data_reliability": {"level": "high", "decision_allowed": True},
        "japan_risk": {"flags": ["foreign_asset_fx_headwind"]},
        "score": {"total_score": 0.7},
    }
    blockers = build_buy_blocker_breakdown(report)
    payload = build_buy_readiness_score(report, blockers)

    assert 0 <= payload["buy_readiness_score"] <= 100
    assert payload["affects_final_action"] is False
    assert "FX risk is blocking buy clarity" in payload["negative_factors"]


def test_buy_readiness_score_penalizes_low_data_quality() -> None:
    payload = build_buy_readiness_score(
        {
            "spot_signal": {"action_layers": {"market_raw_action": "wait", "risk_adjusted_action": "wait", "final_action": "wait"}},
            "risk_lines": {"stage_key": "normal"},
            "data_reliability": {"level": "low", "decision_allowed": False},
            "score": {"total_score": 0.2},
        }
    )

    assert payload["readiness_level"] == "far"
    assert payload["buy_readiness_score"] <= 10


def test_caution_watch_case_does_not_collapse_to_near_zero() -> None:
    report = _watch_with_caution_blockers()
    blockers = build_buy_blocker_breakdown(report)
    payload = build_buy_readiness_score(report, blockers)

    assert report["spot_signal"]["action_layers"] == {
        "market_raw_action": "watch",
        "risk_adjusted_action": "watch",
        "final_action": "watch",
    }
    assert report["risk_lines"]["stage_key"] == "normal"
    assert blockers["blocker_severity"] == {"rate_shock": "caution", "fx_risk": "caution", "score_shortfall": "medium"}
    assert payload["buy_readiness_score"] == 31
    assert 25 <= payload["buy_readiness_score"] <= 45
    assert payload["affects_final_action"] is False


def test_true_high_rate_and_credit_stress_remain_low() -> None:
    report = _watch_with_caution_blockers()
    report["spot_signal"]["blocker_assessment"]["flags"] = [
        "rate_shock_active",
        "credit_stress_active",
        "japan_fx_risk_moderate",
    ]
    blockers = build_buy_blocker_breakdown(report)
    payload = build_buy_readiness_score(report, blockers)

    assert blockers["blocker_severity"]["rate_shock"] == "high"
    assert blockers["blocker_severity"]["credit_stress"] == "high"
    assert payload["buy_readiness_score"] <= 15


def test_score_shortfall_only_watch_case_is_not_over_penalized() -> None:
    report = _watch_with_caution_blockers()
    report["spot_signal"]["blocker_assessment"]["flags"] = []
    blockers = build_buy_blocker_breakdown(report)
    payload = build_buy_readiness_score(report, blockers)

    assert blockers["blocker_rank"] == ["score_shortfall"]
    assert payload["buy_readiness_score"] == 49
    assert 35 <= payload["buy_readiness_score"] <= 55


def test_fx_caution_only_is_not_over_penalized() -> None:
    report = _watch_with_caution_blockers()
    report["spot_signal"]["blocker_assessment"]["flags"] = ["japan_fx_risk_moderate"]
    report["score"]["total_score"] = 0.7
    blockers = build_buy_blocker_breakdown(report)
    payload = build_buy_readiness_score(report, blockers)

    assert blockers["blocker_severity"] == {"fx_risk": "caution"}
    assert payload["buy_readiness_score"] == 43


def test_sample_fallback_remains_low_even_with_positive_context() -> None:
    report = _watch_with_caution_blockers()
    report["spot_signal"]["blocker_assessment"]["flags"] = []
    report["data_reliability"]["sample_fallback_count"] = 1
    blockers = build_buy_blocker_breakdown(report)
    payload = build_buy_readiness_score(report, blockers)

    assert blockers["primary_blocker"] == "sample_only"
    assert payload["buy_readiness_score"] <= 10


def test_hard_data_quality_cap_remains_low_with_positive_context() -> None:
    report = _watch_with_caution_blockers()
    report["spot_signal"]["blocker_assessment"]["flags"] = []
    report["data_reliability"] = {"level": "low", "decision_allowed": False}
    blockers = build_buy_blocker_breakdown(report)
    payload = build_buy_readiness_score(report, blockers)

    assert blockers["primary_blocker"] == "data_quality"
    assert payload["buy_readiness_score"] <= 10
