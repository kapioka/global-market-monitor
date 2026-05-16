from __future__ import annotations

import numpy as np
import pandas as pd

from project.indicators import atr_from_closes, drawdown_series, max_drawdown, momentum, rate_of_change, ratio_series, rolling_rate_of_change_zscore, rolling_zscore


def test_drawdown_series_starts_at_zero_or_above():
    prices = pd.Series([100, 105, 95, 110], dtype=float)
    dd = drawdown_series(prices)
    assert dd.iloc[0] == 0
    assert dd.min() <= 0


def test_max_drawdown_detects_peak_to_trough():
    prices = pd.Series([100, 120, 90, 130], dtype=float)
    assert round(max_drawdown(prices), 4) == -0.25


def test_atr_from_closes_positive_for_variable_series():
    prices = pd.Series(np.linspace(100, 120, 30) + np.sin(np.arange(30)))
    assert atr_from_closes(prices, window=14) > 0


def test_momentum_positive_for_rising_series():
    prices = pd.Series(np.linspace(100, 130, 20))
    assert momentum(prices, window=12) > 0


def test_ratio_series_divides_aligned_points():
    base = pd.Series([100.0, 105.0, 110.0])
    benchmark = pd.Series([50.0, 50.0, 55.0])
    ratio = ratio_series(base, benchmark)
    assert ratio.iloc[-1] == 2.0


def test_rate_of_change_uses_requested_window():
    prices = pd.Series([100.0, 105.0, 110.0, 121.0])
    assert round(rate_of_change(prices, 1), 4) == 0.1
    assert round(rate_of_change(prices, 3), 4) == 0.21


def test_rolling_zscore_returns_positive_value_for_rising_tail():
    prices = pd.Series([10.0, 11.0, 12.0, 13.0, 15.0])
    assert rolling_zscore(prices, 5) > 0


def test_rolling_rate_of_change_zscore_reflects_outlier_move():
    prices = pd.Series([100.0] * 10 + [95.0], dtype=float)
    assert rolling_rate_of_change_zscore(prices, change_window=1, zscore_window=5) < 0
