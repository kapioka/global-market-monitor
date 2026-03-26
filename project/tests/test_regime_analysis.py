from __future__ import annotations

import numpy as np
import pandas as pd

from project.regime_analysis import analyze_market_regime


def test_regime_analysis_promotes_credit_stress_when_credit_flag_is_bad():
    prices = pd.DataFrame({"ACWI": np.linspace(100, 90, 80)})
    returns = prices.pct_change()
    credit_monitor = [
        {"ticker": "HYG", "signal_label": "弱含み", "change_4w": -0.03},
        {"ticker": "HYG/LQD", "signal_label": "信用収縮警戒", "change_4w": -0.04},
    ]
    thresholds = {
        "adx_trend_strong": 25,
        "drawdown_alert": -0.12,
        "volatility_compression_ratio": 0.85,
        "regime_risk_off_score": -0.2,
        "regime_risk_on_score": 0.2,
    }

    regime = analyze_market_regime(prices, returns, credit_monitor, [], thresholds)

    assert regime["regime_label"] == "credit_stress"
    assert regime["credit_regime_flag"] == "credit_stress_severe"


def test_regime_analysis_can_mark_early_recovery_when_credit_improves():
    prices = pd.DataFrame({"ACWI": pd.Series(np.linspace(100, 130, 80) + np.sin(np.arange(80)))})
    returns = prices.pct_change()
    credit_monitor = [
        {"ticker": "HYG", "signal_label": "中立", "change_4w": 0.01},
        {"ticker": "HYG/LQD", "signal_label": "信用改善", "change_4w": 0.03},
    ]
    thresholds = {
        "adx_trend_strong": 25,
        "drawdown_alert": -0.12,
        "volatility_compression_ratio": 0.85,
        "regime_risk_off_score": -0.2,
        "regime_risk_on_score": 0.9,
    }

    regime = analyze_market_regime(prices, returns, credit_monitor, [], thresholds)

    assert regime["regime_label"] == "early_recovery"
    assert regime["credit_regime_flag"] == "credit_improving"


def test_regime_analysis_can_mark_inflation_shock():
    prices = pd.DataFrame({"ACWI": pd.Series(np.linspace(110, 100, 80) + np.sin(np.arange(80)))})
    returns = prices.pct_change()
    thresholds = {
        "adx_trend_strong": 25,
        "drawdown_alert": -0.12,
        "volatility_compression_ratio": 0.85,
        "regime_risk_off_score": -0.2,
        "regime_risk_on_score": 0.2,
    }
    inflation_monitor = [
        {"ticker": "CL=F", "signal_label": "インフレ圧力上昇", "change_4w": 0.09},
        {"ticker": "DX-Y.NYB", "signal_label": "ドル高進行", "change_4w": 0.03},
    ]

    regime = analyze_market_regime(prices, returns, [], inflation_monitor, thresholds)

    assert regime["regime_label"] == "inflation_shock"
    assert regime["inflation_regime_flag"] == "inflation_shock_broad"


def test_regime_analysis_applies_sector_vector_support_as_auxiliary_input():
    prices = pd.DataFrame({"ACWI": pd.Series(np.linspace(100, 115, 80) + np.sin(np.arange(80)) * 0.2)})
    returns = prices.pct_change()
    thresholds = {
        "adx_trend_strong": 25,
        "drawdown_alert": -0.12,
        "volatility_compression_ratio": 0.85,
        "regime_risk_off_score": -0.2,
        "regime_risk_on_score": 0.35,
    }

    regime = analyze_market_regime(
        prices,
        returns,
        [],
        [],
        thresholds,
        sector_rotation={"integration_signals": {"cyclical_improving": True, "broad_improvement": True}, "internal_structure": {"structure_label": "Broad Improvement"}},
        sector_config={"regime_bonus_weight": 0.04},
    )

    assert regime["sector_vector_adjustment"] > 0
    assert regime["adjusted_regime_score"] > regime["regime_score"]


def test_regime_analysis_caps_sector_adjustment():
    prices = pd.DataFrame({"ACWI": pd.Series(np.linspace(100, 118, 80) + np.sin(np.arange(80)) * 0.2)})
    returns = prices.pct_change().dropna()
    result = analyze_market_regime(
        prices,
        returns,
        credit_monitor=[],
        inflation_monitor=[],
        thresholds={"adx_trend_strong": 25, "drawdown_alert": -0.12, "volatility_compression_ratio": 0.85, "regime_risk_off_score": -0.2, "regime_risk_on_score": 0.35},
        sector_rotation={
            "integration_signals": {
                "cyclical_improving": True,
                "broad_improvement": True,
                "defensive_leadership": False,
                "peakout_warning": False,
            }
        },
        sector_config={"regime_bonus_weight": 0.2, "max_sector_adjustment": 0.1},
    )
    assert result["sector_vector_adjustment"] == 0.1


def test_regime_analysis_softens_score_on_energy_dominance_warning():
    prices = pd.DataFrame({"ACWI": pd.Series(np.linspace(100, 115, 80) + np.sin(np.arange(80)) * 0.2)})
    returns = prices.pct_change()
    thresholds = {
        "adx_trend_strong": 25,
        "drawdown_alert": -0.12,
        "volatility_compression_ratio": 0.85,
        "regime_risk_off_score": -0.2,
        "regime_risk_on_score": 0.35,
    }
    baseline = analyze_market_regime(prices, returns, [], [], thresholds)
    adjusted = analyze_market_regime(
        prices,
        returns,
        [],
        [],
        thresholds,
        sector_rotation={"integration_signals": {"energy_dominance_warning": True}},
        sector_config={"regime_bonus_weight": 0.05},
    )
    assert adjusted["adjusted_regime_score"] < baseline["adjusted_regime_score"]


def test_regime_analysis_softens_score_on_single_sector_dominance_warning():
    prices = pd.DataFrame({"ACWI": pd.Series(np.linspace(100, 115, 80) + np.sin(np.arange(80)) * 0.2)})
    returns = prices.pct_change()
    thresholds = {
        "adx_trend_strong": 25,
        "drawdown_alert": -0.12,
        "volatility_compression_ratio": 0.85,
        "regime_risk_off_score": -0.2,
        "regime_risk_on_score": 0.35,
    }
    baseline = analyze_market_regime(prices, returns, [], [], thresholds)
    adjusted = analyze_market_regime(
        prices,
        returns,
        [],
        [],
        thresholds,
        sector_rotation={"integration_signals": {"single_sector_dominance_warning": True}},
        sector_config={"regime_bonus_weight": 0.05},
    )
    assert adjusted["adjusted_regime_score"] < baseline["adjusted_regime_score"]


def test_regime_analysis_allows_more_dominance_in_risk_on_than_risk_off():
    prices = pd.DataFrame({"ACWI": pd.Series(np.linspace(100, 115, 80) + np.sin(np.arange(80)) * 0.2)})
    returns = prices.pct_change()
    thresholds = {
        "adx_trend_strong": 25,
        "drawdown_alert": -0.12,
        "volatility_compression_ratio": 0.85,
        "regime_risk_off_score": -0.2,
        "regime_risk_on_score": 0.35,
    }
    risk_on_like = analyze_market_regime(prices, returns, [], [], thresholds, sector_rotation={"integration_signals": {"single_sector_dominance_warning": True}}, sector_config={"regime_bonus_weight": 0.05})
    risk_off = analyze_market_regime(prices * 0.85, (prices * 0.85).pct_change(), [], [], thresholds, sector_rotation={"integration_signals": {"single_sector_dominance_warning": True}}, sector_config={"regime_bonus_weight": 0.05})
    assert abs(risk_on_like["sector_vector_adjustment"]) <= abs(risk_off["sector_vector_adjustment"])


def test_regime_analysis_returns_explain_log_for_sector_adjustment():
    prices = pd.DataFrame({"ACWI": pd.Series(np.linspace(100, 115, 80) + np.sin(np.arange(80)) * 0.2)})
    returns = prices.pct_change()
    thresholds = {"adx_trend_strong": 25, "drawdown_alert": -0.12, "volatility_compression_ratio": 0.85, "regime_risk_off_score": -0.2, "regime_risk_on_score": 0.35}
    regime = analyze_market_regime(prices, returns, [], [], thresholds, sector_rotation={"integration_signals": {"broad_improvement": True, "cyclical_improving": True}})
    assert regime["sector_adjustment_explain"]


def test_regime_analysis_penalizes_strong_dominance_more_than_weak():
    prices = pd.DataFrame({"ACWI": pd.Series(np.linspace(100, 115, 80) + np.sin(np.arange(80)) * 0.2)})
    returns = prices.pct_change()
    thresholds = {
        "adx_trend_strong": 25,
        "drawdown_alert": -0.12,
        "volatility_compression_ratio": 0.85,
        "regime_risk_off_score": -0.2,
        "regime_risk_on_score": 0.35,
    }
    weak = analyze_market_regime(prices, returns, [], [], thresholds, sector_rotation={"integration_signals": {"single_sector_dominance_warning": True, "dominance_strength": "weak"}}, sector_config={"regime_bonus_weight": 0.05})
    strong = analyze_market_regime(prices, returns, [], [], thresholds, sector_rotation={"integration_signals": {"single_sector_dominance_warning": True, "dominance_strength": "strong"}}, sector_config={"regime_bonus_weight": 0.05})
    assert abs(strong["sector_vector_adjustment"]) > abs(weak["sector_vector_adjustment"])
