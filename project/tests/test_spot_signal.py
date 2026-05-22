from __future__ import annotations

from project.spot_signal import evaluate_spot_signal


def test_spot_signal_buy_window_for_strong_score():
    score = {"total_score": 0.8, "credit_stress_component": 0.7}
    regime = {"regime_label": "risk_on", "max_drawdown": -0.05}
    cycle = {"phase_label": "recovery"}
    credit_monitor = [{"ticker": "HYG/LQD", "signal_label": "信用改善"}]
    inflation_monitor = [{"ticker": "CL=F", "signal_label": "中立"}]
    thresholds = {
        "spot_score_buy": 0.65,
        "spot_score_watch": 0.45,
        "drawdown_alert": -0.12,
        "penalty_transition": 0.03,
        "penalty_risk_off": 0.08,
        "penalty_risk_off_relief": 0.02,
        "penalty_risk_off_relief_score_min": 0.48,
        "penalty_credit_stress_moderate": 0.14,
        "penalty_credit_stress_severe": 0.18,
        "penalty_credit_stress": 0.18,
        "penalty_inflation_shock_oil_only": 0.06,
        "penalty_inflation_shock_broad": 0.12,
        "penalty_inflation_shock": 0.12,
        "penalty_stagflation_warning": 0.2,
    }
    result = evaluate_spot_signal(score, regime, cycle, credit_monitor, inflation_monitor, thresholds)
    assert result["action"] == "buy_window"
    assert result["action_layers"]["market_raw_action"] == "buy_window"
    assert result["action_layers"]["risk_adjusted_action"] == "buy_window"
    assert result["action_layers"]["final_action"] == "buy_window"
    assert result["action_decision"]["raw_action"] == "buy_window"
    assert result["action_decision"]["reliability_cap_applied"] is False
    assert "インフレ" in result["rationale"][-1]
    assert result["adjusted_score"] == 0.8


def test_spot_signal_caps_buy_window_to_watch_when_reliability_requires_it():
    result = evaluate_spot_signal(
        score={"total_score": 0.8, "credit_stress_component": 0.7},
        regime={"regime_label": "risk_on", "max_drawdown": -0.05},
        cycle={"phase_label": "recovery"},
        credit_monitor=[{"ticker": "HYG/LQD", "signal_label": "信用改善"}],
        inflation_monitor=[],
        thresholds={
            "spot_score_buy": 0.65,
            "spot_score_watch": 0.45,
            "drawdown_alert": -0.12,
            "penalty_transition": 0.03,
            "penalty_risk_off": 0.08,
            "penalty_risk_off_relief": 0.02,
            "penalty_risk_off_relief_score_min": 0.48,
            "penalty_credit_stress_moderate": 0.14,
            "penalty_credit_stress_severe": 0.18,
            "penalty_credit_stress": 0.18,
            "penalty_inflation_shock_oil_only": 0.06,
            "penalty_inflation_shock_broad": 0.12,
            "penalty_inflation_shock": 0.12,
            "penalty_stagflation_warning": 0.2,
        },
        recovery_evidence={"score": 0.82, "grade": "confirmed", "summary": "回復確認は強めです。"},
        reliability_policy={
            "max_action": "watch",
            "confidence_cap": 0.45,
            "degrade_reasons": ["sample_fallback_present"],
            "blocking_reasons": [],
        },
    )

    assert result["action"] == "watch"
    assert result["action_layers"]["market_raw_action"] == "buy_window"
    assert result["action_layers"]["risk_adjusted_action"] == "buy_window"
    assert result["action_layers"]["final_action"] == "watch"
    assert result["action_decision"]["raw_action"] == "buy_window"
    assert result["action_decision"]["action"] == "watch"
    assert result["action_decision"]["confidence"] == 0.45
    assert result["action_decision"]["raw_confidence"] == 0.82
    assert result["action_decision"]["reliability_cap_applied"] is True
    assert result["action_decision"]["cap_reason"] == ["sample_fallback_present"]


def test_spot_signal_maps_diagnostic_only_cap_to_wait_action():
    result = evaluate_spot_signal(
        score={"total_score": 0.8, "credit_stress_component": 0.7},
        regime={"regime_label": "risk_on", "max_drawdown": -0.05},
        cycle={"phase_label": "recovery"},
        credit_monitor=[{"ticker": "HYG/LQD", "signal_label": "信用改善"}],
        inflation_monitor=[],
        thresholds={
            "spot_score_buy": 0.65,
            "spot_score_watch": 0.45,
            "drawdown_alert": -0.12,
            "penalty_transition": 0.03,
            "penalty_risk_off": 0.08,
            "penalty_risk_off_relief": 0.02,
            "penalty_risk_off_relief_score_min": 0.48,
            "penalty_credit_stress_moderate": 0.14,
            "penalty_credit_stress_severe": 0.18,
            "penalty_credit_stress": 0.18,
            "penalty_inflation_shock_oil_only": 0.06,
            "penalty_inflation_shock_broad": 0.12,
            "penalty_inflation_shock": 0.12,
            "penalty_stagflation_warning": 0.2,
        },
        recovery_evidence={"score": 0.82, "grade": "confirmed", "summary": "回復確認は強めです。"},
        reliability_policy={
            "max_action": "diagnostic_only",
            "confidence_cap": 0.0,
            "blocking_reasons": ["sample_only"],
            "degrade_reasons": [],
        },
    )

    assert result["action"] == "wait"
    assert result["action_layers"]["final_action"] == "wait"
    assert result["action_decision"]["max_action"] == "diagnostic_only"
    assert result["action_decision"]["confidence"] == 0.0
    assert result["action_decision"]["reliability_cap_applied"] is True


def test_spot_signal_downgrades_inflation_shock_by_penalty():
    score = {"total_score": 0.7, "credit_stress_component": 0.5}
    regime = {"regime_label": "inflation_shock", "inflation_regime_flag": "inflation_shock_broad", "max_drawdown": -0.05}
    cycle = {"phase_label": "late_cycle"}
    credit_monitor = [{"ticker": "HYG/LQD", "signal_label": "中立"}]
    inflation_monitor = [
        {"ticker": "CL=F", "signal_label": "インフレ圧力上昇"},
        {"ticker": "DX-Y.NYB", "signal_label": "ドル高進行"},
    ]
    thresholds = {
        "spot_score_buy": 0.65,
        "spot_score_watch": 0.45,
        "drawdown_alert": -0.12,
        "penalty_transition": 0.03,
        "penalty_risk_off": 0.08,
        "penalty_risk_off_relief": 0.02,
        "penalty_risk_off_relief_score_min": 0.48,
        "penalty_credit_stress_moderate": 0.14,
        "penalty_credit_stress_severe": 0.18,
        "penalty_credit_stress": 0.18,
        "penalty_inflation_shock_oil_only": 0.06,
        "penalty_inflation_shock_broad": 0.12,
        "penalty_inflation_shock": 0.12,
        "penalty_stagflation_warning": 0.2,
    }
    result = evaluate_spot_signal(score, regime, cycle, credit_monitor, inflation_monitor, thresholds)
    assert result["action"] == "watch"
    assert result["regime_penalty"] == 0.12
    assert result["adjusted_score"] == 0.58


def test_spot_signal_applies_japan_fx_risk_penalty():
    result = evaluate_spot_signal(
        score={"total_score": 0.67, "credit_stress_component": 0.6},
        regime={"regime_label": "risk_on", "max_drawdown": -0.04},
        cycle={"phase_label": "upswing"},
        credit_monitor=[],
        inflation_monitor=[],
        thresholds={
            "spot_score_buy": 0.65,
            "spot_score_watch": 0.45,
            "drawdown_alert": -0.12,
            "penalty_transition": 0.02,
            "penalty_risk_off": 0.06,
            "penalty_risk_off_relief": 0.02,
            "penalty_risk_off_relief_score_min": 0.48,
            "penalty_credit_stress_moderate": 0.12,
            "penalty_credit_stress_severe": 0.16,
            "penalty_credit_stress": 0.16,
            "penalty_inflation_shock_oil_only": 0.06,
            "penalty_inflation_shock_broad": 0.1,
            "penalty_inflation_shock": 0.1,
            "penalty_stagflation_warning": 0.18,
        },
        recovery_evidence={"score": 0.72, "grade": "confirmed", "summary": "回復確認は強めです。"},
        japan_risk={
            "level": "high",
            "flags": ["fx_shock", "foreign_asset_fx_dependency"],
            "summary": "USDJPY は円安急進です。",
        },
        japan_risk_config={"spot_penalty_high": 0.04},
    )

    assert result["japan_risk_penalty"] == 0.04
    assert result["adjusted_score"] == 0.63
    assert result["action"] == "watch"
    assert "japan_fx_risk_high" in result["blocker_assessment"]["flags"]


def test_spot_signal_applies_relief_penalty_for_high_score_risk_off():
    score = {"total_score": 0.49, "credit_stress_component": 0.5}
    regime = {"regime_label": "risk_off", "max_drawdown": -0.05}
    cycle = {"phase_label": "late_cycle"}
    credit_monitor = [{"ticker": "HYG/LQD", "signal_label": "中立"}]
    inflation_monitor = [{"ticker": "CL=F", "signal_label": "中立"}]
    thresholds = {
        "spot_score_buy": 0.65,
        "spot_score_watch": 0.45,
        "drawdown_alert": -0.12,
        "penalty_transition": 0.02,
        "penalty_risk_off": 0.06,
        "penalty_risk_off_relief": 0.02,
        "penalty_risk_off_relief_score_min": 0.48,
        "penalty_credit_stress_moderate": 0.12,
        "penalty_credit_stress_severe": 0.16,
        "penalty_credit_stress": 0.16,
        "penalty_inflation_shock_oil_only": 0.06,
        "penalty_inflation_shock_broad": 0.1,
        "penalty_inflation_shock": 0.1,
        "penalty_stagflation_warning": 0.18,
    }
    result = evaluate_spot_signal(score, regime, cycle, credit_monitor, inflation_monitor, thresholds)
    assert result["regime_penalty"] == 0.02
    assert result["adjusted_score"] == 0.47
    assert result["action"] == "wait"
    assert result["legacy_action"] == "watch"
    assert result["action_decision"]["action"] == "wait"
    assert result["risk_off_relief_applied"] is True


def test_spot_signal_uses_moderate_credit_penalty_tier():
    score = {"total_score": 0.62, "credit_stress_component": 0.3}
    regime = {"regime_label": "credit_stress", "credit_regime_flag": "credit_stress_moderate", "max_drawdown": -0.05}
    cycle = {"phase_label": "late_cycle"}
    thresholds = {
        "spot_score_buy": 0.65,
        "spot_score_watch": 0.45,
        "drawdown_alert": -0.12,
        "penalty_transition": 0.02,
        "penalty_risk_off": 0.06,
        "penalty_risk_off_relief": 0.02,
        "penalty_risk_off_relief_score_min": 0.48,
        "penalty_credit_stress_moderate": 0.12,
        "penalty_credit_stress_severe": 0.16,
        "penalty_credit_stress": 0.16,
        "penalty_inflation_shock_oil_only": 0.06,
        "penalty_inflation_shock_broad": 0.1,
        "penalty_inflation_shock": 0.1,
        "penalty_stagflation_warning": 0.18,
    }
    result = evaluate_spot_signal(score, regime, cycle, [], [], thresholds)
    assert result["regime_penalty"] == 0.12
    assert result["adjusted_score"] == 0.5
    assert result["action"] == "wait"
    assert result["legacy_action"] == "watch"
    assert result["action_decision"]["action"] == "wait"


def test_spot_signal_uses_sector_structure_as_small_auxiliary_adjustment():
    score = {"total_score": 0.64, "credit_stress_component": 0.5}
    regime = {"regime_label": "risk_on", "max_drawdown": -0.05}
    cycle = {"phase_label": "upswing"}
    thresholds = {
        "spot_score_buy": 0.65,
        "spot_score_watch": 0.45,
        "drawdown_alert": -0.12,
        "penalty_transition": 0.02,
        "penalty_risk_off": 0.06,
        "penalty_risk_off_relief": 0.02,
        "penalty_risk_off_relief_score_min": 0.48,
        "penalty_credit_stress_moderate": 0.12,
        "penalty_credit_stress_severe": 0.16,
        "penalty_credit_stress": 0.16,
        "penalty_inflation_shock_oil_only": 0.06,
        "penalty_inflation_shock_broad": 0.1,
        "penalty_inflation_shock": 0.1,
        "penalty_stagflation_warning": 0.18,
    }
    result = evaluate_spot_signal(
        score,
        regime,
        cycle,
        [],
        [],
        thresholds,
        sector_rotation={"integration_signals": {"broad_improvement": True}, "internal_structure": {"structure_label": "Broad Improvement"}},
        sector_config={"spot_signal_integration_weight": 0.02},
    )
    assert result["sector_adjustment"] > 0
    assert result["adjusted_score"] > score["total_score"]
    assert result["action"] == "buy_window"


def test_spot_signal_caps_sector_adjustment():
    result = evaluate_spot_signal(
        score={"total_score": 0.6, "credit_stress_component": 0.5},
        regime={
            "regime_label": "transition",
            "max_drawdown": -0.04,
            "credit_regime_flag": "neutral",
            "inflation_regime_flag": "neutral",
        },
        cycle={"phase_label": "recovery"},
        credit_monitor=[],
        inflation_monitor=[],
        thresholds={"spot_score_buy": 0.65, "spot_score_watch": 0.45, "penalty_transition": 0.03},
        sector_rotation={
            "integration_signals": {
                "broad_improvement": True,
                "cyclical_improving": True,
                "peakout_warning": False,
                "defensive_leadership": False,
            },
            "internal_structure": {"structure_label": "Broad Improvement"},
        },
        sector_config={"spot_signal_integration_weight": 0.08, "max_sector_adjustment": 0.1},
    )
    assert result["sector_adjustment"] == 0.1


def test_spot_signal_weakens_on_energy_dominance_warning():
    score = {"total_score": 0.64, "credit_stress_component": 0.5}
    regime = {"regime_label": "risk_on", "max_drawdown": -0.05}
    cycle = {"phase_label": "upswing"}
    thresholds = {
        "spot_score_buy": 0.65,
        "spot_score_watch": 0.45,
        "drawdown_alert": -0.12,
        "penalty_transition": 0.02,
        "penalty_risk_off": 0.06,
        "penalty_risk_off_relief": 0.02,
        "penalty_risk_off_relief_score_min": 0.48,
        "penalty_credit_stress_moderate": 0.12,
        "penalty_credit_stress_severe": 0.16,
        "penalty_credit_stress": 0.16,
        "penalty_inflation_shock_oil_only": 0.06,
        "penalty_inflation_shock_broad": 0.1,
        "penalty_inflation_shock": 0.1,
        "penalty_stagflation_warning": 0.18,
    }
    result = evaluate_spot_signal(
        score,
        regime,
        cycle,
        [],
        [],
        thresholds,
        sector_rotation={"integration_signals": {"energy_dominance_warning": True}, "internal_structure": {"structure_label": "Narrow Leadership"}},
        sector_config={"spot_signal_integration_weight": 0.02},
    )
    assert result["sector_adjustment"] < 0
    assert result["adjusted_score"] < score["total_score"]


def test_spot_signal_weakens_on_single_sector_dominance_warning():
    score = {"total_score": 0.64, "credit_stress_component": 0.5}
    regime = {"regime_label": "risk_on", "max_drawdown": -0.05}
    cycle = {"phase_label": "upswing"}
    thresholds = {
        "spot_score_buy": 0.65,
        "spot_score_watch": 0.45,
        "drawdown_alert": -0.12,
        "penalty_transition": 0.02,
        "penalty_risk_off": 0.06,
        "penalty_risk_off_relief": 0.02,
        "penalty_risk_off_relief_score_min": 0.48,
        "penalty_credit_stress_moderate": 0.12,
        "penalty_credit_stress_severe": 0.16,
        "penalty_credit_stress": 0.16,
        "penalty_inflation_shock_oil_only": 0.06,
        "penalty_inflation_shock_broad": 0.1,
        "penalty_inflation_shock": 0.1,
        "penalty_stagflation_warning": 0.18,
    }
    result = evaluate_spot_signal(
        score,
        regime,
        cycle,
        [],
        [],
        thresholds,
        sector_rotation={"integration_signals": {"single_sector_dominance_warning": True}, "internal_structure": {"structure_label": "Narrow Leadership"}},
        sector_config={"spot_signal_integration_weight": 0.02},
    )
    assert result["sector_adjustment"] < 0
    assert result["adjusted_score"] < score["total_score"]


def test_spot_signal_penalizes_single_sector_dominance_less_in_risk_on():
    score = {"total_score": 0.64, "credit_stress_component": 0.5}
    cycle = {"phase_label": "upswing"}
    thresholds = {
        "spot_score_buy": 0.65,
        "spot_score_watch": 0.45,
        "drawdown_alert": -0.12,
        "penalty_transition": 0.02,
        "penalty_risk_off": 0.06,
        "penalty_risk_off_relief": 0.02,
        "penalty_risk_off_relief_score_min": 0.48,
        "penalty_credit_stress_moderate": 0.12,
        "penalty_credit_stress_severe": 0.16,
        "penalty_credit_stress": 0.16,
        "penalty_inflation_shock_oil_only": 0.06,
        "penalty_inflation_shock_broad": 0.1,
        "penalty_inflation_shock": 0.1,
        "penalty_stagflation_warning": 0.18,
    }
    risk_on = evaluate_spot_signal(score, {"regime_label": "risk_on", "max_drawdown": -0.05}, cycle, [], [], thresholds, sector_rotation={"integration_signals": {"single_sector_dominance_warning": True}, "internal_structure": {"structure_label": "Narrow Leadership"}}, sector_config={"spot_signal_integration_weight": 0.02})
    risk_off = evaluate_spot_signal(score, {"regime_label": "risk_off", "max_drawdown": -0.05}, cycle, [], [], thresholds, sector_rotation={"integration_signals": {"single_sector_dominance_warning": True}, "internal_structure": {"structure_label": "Narrow Leadership"}}, sector_config={"spot_signal_integration_weight": 0.02})
    assert abs(risk_on["sector_adjustment"]) < abs(risk_off["sector_adjustment"])


def test_spot_signal_returns_sector_adjustment_explain():
    score = {"total_score": 0.64, "credit_stress_component": 0.5}
    regime = {"regime_label": "risk_on", "max_drawdown": -0.05}
    cycle = {"phase_label": "upswing"}
    thresholds = {"spot_score_buy": 0.65, "spot_score_watch": 0.45, "drawdown_alert": -0.12, "penalty_transition": 0.02, "penalty_risk_off": 0.06, "penalty_risk_off_relief": 0.02, "penalty_risk_off_relief_score_min": 0.48, "penalty_credit_stress_moderate": 0.12, "penalty_credit_stress_severe": 0.16, "penalty_credit_stress": 0.16, "penalty_inflation_shock_oil_only": 0.06, "penalty_inflation_shock_broad": 0.1, "penalty_inflation_shock": 0.1, "penalty_stagflation_warning": 0.18}
    result = evaluate_spot_signal(score, regime, cycle, [], [], thresholds, sector_rotation={"integration_signals": {"broad_improvement": True}, "internal_structure": {"structure_label": "Broad Improvement"}})
    assert result["sector_adjustment_explain"]


def test_spot_signal_penalizes_strong_dominance_more_than_weak():
    score = {"total_score": 0.64, "credit_stress_component": 0.5}
    regime = {"regime_label": "transition", "max_drawdown": -0.05}
    cycle = {"phase_label": "upswing"}
    thresholds = {
        "spot_score_buy": 0.65,
        "spot_score_watch": 0.45,
        "drawdown_alert": -0.12,
        "penalty_transition": 0.02,
        "penalty_risk_off": 0.06,
        "penalty_risk_off_relief": 0.02,
        "penalty_risk_off_relief_score_min": 0.48,
        "penalty_credit_stress_moderate": 0.12,
        "penalty_credit_stress_severe": 0.16,
        "penalty_credit_stress": 0.16,
        "penalty_inflation_shock_oil_only": 0.06,
        "penalty_inflation_shock_broad": 0.1,
        "penalty_inflation_shock": 0.1,
        "penalty_stagflation_warning": 0.18,
    }
    weak = evaluate_spot_signal(score, regime, cycle, [], [], thresholds, sector_rotation={"integration_signals": {"single_sector_dominance_warning": True, "dominance_strength": "weak"}, "internal_structure": {"structure_label": "Narrow Leadership"}}, sector_config={"spot_signal_integration_weight": 0.02})
    strong = evaluate_spot_signal(score, regime, cycle, [], [], thresholds, sector_rotation={"integration_signals": {"single_sector_dominance_warning": True, "dominance_strength": "strong"}, "internal_structure": {"structure_label": "Narrow Leadership"}}, sector_config={"spot_signal_integration_weight": 0.02})
    assert abs(strong["sector_adjustment"]) > abs(weak["sector_adjustment"])

def test_spot_signal_returns_structured_parallel_fields():
    score = {"total_score": 0.8, "credit_stress_component": 0.7}
    regime = {"regime_label": "risk_on", "max_drawdown": -0.05}
    cycle = {"phase_label": "recovery"}
    credit_monitor = [{"ticker": "HYG/LQD", "signal_label": "信用改善"}]
    inflation_monitor = [{"ticker": "CL=F", "signal_label": "中立"}]
    thresholds = {
        "spot_score_buy": 0.65,
        "spot_score_watch": 0.45,
        "drawdown_alert": -0.12,
        "penalty_transition": 0.03,
        "penalty_risk_off": 0.08,
        "penalty_risk_off_relief": 0.02,
        "penalty_risk_off_relief_score_min": 0.48,
        "penalty_credit_stress_moderate": 0.14,
        "penalty_credit_stress_severe": 0.18,
        "penalty_credit_stress": 0.18,
        "penalty_inflation_shock_oil_only": 0.06,
        "penalty_inflation_shock_broad": 0.12,
        "penalty_inflation_shock": 0.12,
        "penalty_stagflation_warning": 0.2,
    }
    result = evaluate_spot_signal(score, regime, cycle, credit_monitor, inflation_monitor, thresholds)
    assert result["action"] == "buy_window"
    assert result["recovery_evidence"]["grade"] in {"building", "confirmed"}
    assert result["blocker_assessment"]["level"] == "none"
    assert result["action_decision"]["action"] == "buy_window"
    assert result["legacy_adjusted_score"] == result["adjusted_score"]


def test_spot_signal_structured_decision_can_watch_while_legacy_stays_watch_under_caution():
    score = {"total_score": 0.7, "credit_stress_component": 0.5}
    regime = {"regime_label": "risk_on", "max_drawdown": -0.05, "credit_regime_flag": "neutral"}
    cycle = {"phase_label": "recovery"}
    thresholds = {
        "spot_score_buy": 0.65,
        "spot_score_watch": 0.45,
        "drawdown_alert": -0.12,
        "penalty_transition": 0.03,
        "penalty_risk_off": 0.08,
        "penalty_risk_off_relief": 0.02,
        "penalty_risk_off_relief_score_min": 0.48,
        "penalty_credit_stress_moderate": 0.14,
        "penalty_credit_stress_severe": 0.18,
        "penalty_credit_stress": 0.18,
        "penalty_inflation_shock_oil_only": 0.06,
        "penalty_inflation_shock_broad": 0.12,
        "penalty_inflation_shock": 0.12,
        "penalty_stagflation_warning": 0.2,
    }
    risk_lines = {"stage_key": "credit_spillover_initial", "stage_label": "信用波及初期", "summary": "波及", "decision_level": "caution", "decision_flags": ["credit_spillover_initial"], "decision_summary": "慎重"}
    result = evaluate_spot_signal(score, regime, cycle, [], [], thresholds, risk_lines=risk_lines)
    assert result["action"] == "watch"
    assert result["blocker_assessment"]["level"] == "caution"
    assert result["action_decision"]["action"] == "watch"


def test_spot_signal_structured_decision_blocks_on_extreme_risk():
    score = {"total_score": 0.85, "credit_stress_component": 0.7}
    regime = {"regime_label": "risk_on", "max_drawdown": -0.04, "credit_regime_flag": "neutral"}
    cycle = {"phase_label": "recovery"}
    thresholds = {
        "spot_score_buy": 0.65,
        "spot_score_watch": 0.45,
        "drawdown_alert": -0.12,
        "penalty_transition": 0.03,
        "penalty_risk_off": 0.08,
        "penalty_risk_off_relief": 0.02,
        "penalty_risk_off_relief_score_min": 0.48,
        "penalty_credit_stress_moderate": 0.14,
        "penalty_credit_stress_severe": 0.18,
        "penalty_credit_stress": 0.18,
        "penalty_inflation_shock_oil_only": 0.06,
        "penalty_inflation_shock_broad": 0.12,
        "penalty_inflation_shock": 0.12,
        "penalty_stagflation_warning": 0.2,
    }
    risk_lines = {"stage_key": "extreme_danger_line_reached", "stage_label": "非常に危険ライン到達", "summary": "危険", "decision_level": "block", "decision_flags": ["extreme_market_stress"], "decision_summary": "ブロック"}
    result = evaluate_spot_signal(score, regime, cycle, [], [], thresholds, risk_lines=risk_lines)
    assert result["action"] == "wait"
    assert result["blocker_assessment"]["level"] == "block"
    assert result["action_decision"]["action"] == "wait"


def test_spot_signal_adds_buy_candidate_between_watch_and_buy_window():
    result = evaluate_spot_signal(
        score={"total_score": 0.58, "credit_stress_component": 0.5},
        regime={"regime_label": "risk_on", "max_drawdown": -0.05},
        cycle={"phase_label": "upswing"},
        credit_monitor=[],
        inflation_monitor=[],
        thresholds={
            "spot_score_buy": 0.65,
            "spot_score_watch": 0.45,
            "drawdown_alert": -0.12,
            "penalty_transition": 0.02,
            "penalty_risk_off": 0.06,
            "penalty_risk_off_relief": 0.02,
            "penalty_risk_off_relief_score_min": 0.48,
        },
        recovery_evidence={"score": 0.58, "grade": "building", "summary": "形成中です。"},
        reliability_policy={"max_action": "buy_window", "confidence_cap": 1.0, "degrade_reasons": []},
    )

    assert result["action"] == "buy_candidate"
    assert result["action_layers"]["market_raw_action"] == "buy_candidate"
    assert result["action_layers"]["risk_adjusted_action"] == "buy_candidate"
    assert result["action_layers"]["final_action"] == "buy_candidate"
