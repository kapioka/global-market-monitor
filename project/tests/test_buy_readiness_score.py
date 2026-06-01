from __future__ import annotations

import json
from pathlib import Path

from project.buy_blocker_breakdown import build_buy_blocker_breakdown
from project.buy_readiness_score import build_buy_readiness_score

ACTUAL_CASE_PATH = Path(__file__).parent / "fixtures" / "actual_readiness_case_v0.8.16.json"


def _actual_readiness_case() -> dict:
    return json.loads(ACTUAL_CASE_PATH.read_text(encoding="utf-8"))


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


def test_sanitized_actual_report_fixture_locks_recalibrated_score() -> None:
    case = _actual_readiness_case()
    report = case["report"]
    expected = case["expected"]
    blockers = build_buy_blocker_breakdown(report)
    payload = build_buy_readiness_score(report, blockers)

    assert payload["buy_readiness_score"] == expected["buy_readiness_score"] == 31
    assert expected["score_range"][0] <= payload["buy_readiness_score"] <= expected["score_range"][1]
    assert report["spot_signal"]["action_layers"]["final_action"] == expected["final_action"] == "watch"
    assert report["risk_lines"]["stage_key"] == expected["risk_stage"] == "normal"
    assert blockers["blocker_severity"] == expected["blocker_severity"]


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


def test_actual_watch_fx_caution_and_score_shortfall_calculate_40() -> None:
    report = _watch_with_caution_blockers()
    report["spot_signal"]["blocker_assessment"]["flags"] = [
        "japan_fx_risk_moderate",
        "foreign_asset_fx_dependency",
    ]
    report["score"]["total_score"] = 0.5854
    blockers = build_buy_blocker_breakdown(report)
    payload = build_buy_readiness_score(report, blockers)

    assert blockers["blocker_rank"] == ["fx_risk", "score_shortfall"]
    assert blockers["blocker_severity"] == {"fx_risk": "caution", "score_shortfall": "medium"}
    assert payload["buy_readiness_score"] == 40
    assert payload["readiness_level"] == "watch"


def test_buy_readiness_score_is_not_clamped_to_40() -> None:
    low_report = _watch_with_caution_blockers()
    low_report["spot_signal"]["blocker_assessment"]["flags"] = []
    low_report["data_reliability"]["sample_fallback_count"] = 1
    low_blockers = build_buy_blocker_breakdown(low_report)
    low_payload = build_buy_readiness_score(low_report, low_blockers)

    forty_report = _watch_with_caution_blockers()
    forty_report["spot_signal"]["blocker_assessment"]["flags"] = [
        "japan_fx_risk_moderate",
        "foreign_asset_fx_dependency",
    ]
    forty_report["score"]["total_score"] = 0.5854
    forty_payload = build_buy_readiness_score(forty_report, build_buy_blocker_breakdown(forty_report))

    higher_report = _watch_with_caution_blockers()
    higher_report["spot_signal"]["blocker_assessment"]["flags"] = []
    higher_payload = build_buy_readiness_score(higher_report, build_buy_blocker_breakdown(higher_report))

    assert low_payload["buy_readiness_score"] <= 10
    assert forty_payload["buy_readiness_score"] == 40
    assert higher_payload["buy_readiness_score"] == 49


def test_japan_resident_context_is_excluded_from_buy_readiness_score() -> None:
    report = _watch_with_caution_blockers()
    report["spot_signal"]["blocker_assessment"]["flags"] = [
        "japan_fx_risk_moderate",
        "foreign_asset_fx_dependency",
    ]
    report["score"]["total_score"] = 0.5854
    blockers = build_buy_blocker_breakdown(report)
    baseline = build_buy_readiness_score(report, blockers)

    report["japan_resident_context"] = {
        "jgb_yields": {"jgb_10y": 2.52, "jgb_curve_10y_2y": 1.118},
        "inflation": {"jp_cpi_yoy": 2.7, "jp_cpi_trend": "rising"},
        "domestic_rates": {"boj_call_rate": 0.5, "domestic_rate_context": "rising"},
    }
    report["multi_asset_candidates"] = {
        "affects_buy_readiness_score": False,
        "candidates": [
            {
                "asset_class": "bond_jpy",
                "japan_resident_context_score": 20,
                "japan_resident_must_not_affect_buy_readiness_score": True,
            }
        ],
    }
    with_context = build_buy_readiness_score(report, blockers)

    assert baseline["buy_readiness_score"] == 40
    assert with_context["buy_readiness_score"] == baseline["buy_readiness_score"]
    assert with_context["affects_final_action"] is False


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
