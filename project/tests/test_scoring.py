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
