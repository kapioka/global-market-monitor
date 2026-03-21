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
