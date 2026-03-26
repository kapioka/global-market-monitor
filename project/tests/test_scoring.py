from __future__ import annotations

from project.scoring import score_market


def test_score_market_stays_in_zero_to_one_band():
    regime = {
        "trend_strength": 30,
        "momentum_12w": 0.08,
        "regime_label": "risk_on",
        "max_drawdown": -0.05,
        "volatility_compression": 0.7,
    }
    cycle = {"phase_label": "upswing"}
    credit_monitor = [
        {"ticker": "HYG", "change_4w": 0.03, "zscore": 0.6},
        {"ticker": "LQD", "change_4w": 0.01, "zscore": 0.2},
        {"ticker": "HYG/LQD", "change_4w": 0.02, "zscore": 0.7},
    ]
    weights = {
        "trend": 0.22,
        "momentum": 0.18,
        "breadth_proxy": 0.13,
        "drawdown": 0.13,
        "volatility": 0.14,
        "macro_proxy": 0.1,
        "credit_stress": 0.1,
    }
    thresholds = {
        "adx_trend_strong": 25,
        "volatility_compression_ratio": 0.85,
    }
    score = score_market(regime, cycle, credit_monitor, weights, thresholds)
    assert 0 <= score["total_score"] <= 1
    assert 0 <= score["credit_stress_component"] <= 1


def test_score_market_adds_small_sector_integration_component():
    regime = {
        "trend_strength": 30,
        "momentum_12w": 0.08,
        "regime_label": "risk_on",
        "max_drawdown": -0.05,
        "volatility_compression": 0.7,
    }
    cycle = {"phase_label": "upswing"}
    weights = {
        "trend": 0.22,
        "momentum": 0.18,
        "breadth_proxy": 0.13,
        "drawdown": 0.13,
        "volatility": 0.14,
        "macro_proxy": 0.1,
        "credit_stress": 0.1,
    }
    thresholds = {
        "adx_trend_strong": 25,
        "volatility_compression_ratio": 0.85,
    }
    score = score_market(
        regime,
        cycle,
        [],
        weights,
        thresholds,
        sector_rotation={"integration_signals": {"broad_improvement": True, "cyclical_improving": True}},
        sector_config={"ranking_integration_weight": 0.02},
    )
    assert score["sector_integration_component"] > 0.5
    assert 0 <= score["total_score"] <= 1


def test_score_market_reduces_sector_component_on_energy_dominance_warning():
    regime = {
        "trend_strength": 30,
        "momentum_12w": 0.08,
        "regime_label": "risk_on",
        "max_drawdown": -0.05,
        "volatility_compression": 0.7,
    }
    cycle = {"phase_label": "upswing"}
    weights = {
        "trend": 0.22,
        "momentum": 0.18,
        "breadth_proxy": 0.13,
        "drawdown": 0.13,
        "volatility": 0.14,
        "macro_proxy": 0.1,
        "credit_stress": 0.1,
    }
    thresholds = {"adx_trend_strong": 25, "volatility_compression_ratio": 0.85}
    score = score_market(
        regime,
        cycle,
        [],
        weights,
        thresholds,
        sector_rotation={"integration_signals": {"energy_dominance_warning": True}},
        sector_config={"ranking_integration_weight": 0.02},
    )
    assert score["sector_integration_component"] < 0.5


def test_score_market_reduces_sector_component_on_single_sector_dominance_warning():
    regime = {
        "trend_strength": 30,
        "momentum_12w": 0.08,
        "regime_label": "risk_on",
        "max_drawdown": -0.05,
        "volatility_compression": 0.7,
    }
    cycle = {"phase_label": "upswing"}
    weights = {
        "trend": 0.22,
        "momentum": 0.18,
        "breadth_proxy": 0.13,
        "drawdown": 0.13,
        "volatility": 0.14,
        "macro_proxy": 0.1,
        "credit_stress": 0.1,
    }
    thresholds = {"adx_trend_strong": 25, "volatility_compression_ratio": 0.85}
    score = score_market(
        regime,
        cycle,
        [],
        weights,
        thresholds,
        sector_rotation={"integration_signals": {"single_sector_dominance_warning": True}},
        sector_config={"ranking_integration_weight": 0.02},
    )
    assert score["sector_integration_component"] < 0.5


def test_score_market_penalizes_single_sector_dominance_less_in_risk_on():
    base = {"trend_strength": 30, "momentum_12w": 0.08, "max_drawdown": -0.05, "volatility_compression": 0.7}
    cycle = {"phase_label": "upswing"}
    weights = {"trend": 0.22, "momentum": 0.18, "breadth_proxy": 0.13, "drawdown": 0.13, "volatility": 0.14, "macro_proxy": 0.1, "credit_stress": 0.1}
    thresholds = {"adx_trend_strong": 25, "volatility_compression_ratio": 0.85}
    risk_on_score = score_market({**base, "regime_label": "risk_on"}, cycle, [], weights, thresholds, sector_rotation={"integration_signals": {"single_sector_dominance_warning": True}})
    risk_off_score = score_market({**base, "regime_label": "risk_off"}, cycle, [], weights, thresholds, sector_rotation={"integration_signals": {"single_sector_dominance_warning": True}})
    assert risk_on_score["sector_integration_component"] > risk_off_score["sector_integration_component"]


def test_score_market_returns_sector_integration_explain():
    regime = {"trend_strength": 30, "momentum_12w": 0.08, "regime_label": "risk_on", "max_drawdown": -0.05, "volatility_compression": 0.7}
    cycle = {"phase_label": "upswing"}
    weights = {"trend": 0.22, "momentum": 0.18, "breadth_proxy": 0.13, "drawdown": 0.13, "volatility": 0.14, "macro_proxy": 0.1, "credit_stress": 0.1}
    thresholds = {"adx_trend_strong": 25, "volatility_compression_ratio": 0.85}
    score = score_market(regime, cycle, [], weights, thresholds, sector_rotation={"integration_signals": {"broad_improvement": True}})
    assert score["sector_integration_explain"]


def test_score_market_penalizes_strong_dominance_more_than_weak():
    base = {"trend_strength": 30, "momentum_12w": 0.08, "max_drawdown": -0.05, "volatility_compression": 0.7, "regime_label": "transition"}
    cycle = {"phase_label": "upswing"}
    weights = {"trend": 0.22, "momentum": 0.18, "breadth_proxy": 0.13, "drawdown": 0.13, "volatility": 0.14, "macro_proxy": 0.1, "credit_stress": 0.1}
    thresholds = {"adx_trend_strong": 25, "volatility_compression_ratio": 0.85}
    weak = score_market(base, cycle, [], weights, thresholds, sector_rotation={"integration_signals": {"single_sector_dominance_warning": True, "dominance_strength": "weak"}})
    strong = score_market(base, cycle, [], weights, thresholds, sector_rotation={"integration_signals": {"single_sector_dominance_warning": True, "dominance_strength": "strong"}})
    assert strong["sector_integration_component"] < weak["sector_integration_component"]
