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
    assert "インフレ" in result["rationale"][-1]
    assert result["adjusted_score"] == 0.8


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
    assert result["action"] == "watch"
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
    assert result["action"] == "watch"


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
