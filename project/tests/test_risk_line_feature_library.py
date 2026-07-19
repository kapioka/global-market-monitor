from __future__ import annotations

import warnings

import pandas as pd
import pytest

from project.risk_line_feature_library import build_risk_line_feature_frames


@pytest.mark.parametrize(
    "values",
    [
        [100.0, 101.0, 103.0, 99.0],
        [100.0, None, 110.0, 105.0, None, 120.0],
        [None, 100.0, 105.0, 110.0],
        [100.0, None, None, 108.0, 112.0],
        [None, None, None, None],
        [None, None, 100.0, None],
    ],
)
def test_explicit_forward_fill_pct_change_matches_legacy_contract(values):
    series = pd.Series(values, dtype=float)
    filled = series.ffill()
    legacy_expected = filled.div(filled.shift(1)).sub(1.0)
    explicit_compatible = series.ffill().pct_change(fill_method=None)

    pd.testing.assert_series_equal(legacy_expected, explicit_compatible)


def test_build_risk_line_feature_frames_returns_all_ten_indicator_frames():
    index = pd.date_range("2020-01-03", periods=140, freq="W-FRI")
    prices = pd.DataFrame(
        {
            "SPY": [100.0 + i * 0.4 for i in range(140)],
            "HYG": [80.0 + i * 0.08 for i in range(140)],
            "LQD": [100.0 + i * 0.03 for i in range(140)],
            "^VIX": [18.0 + (i % 7) * 0.6 for i in range(140)],
            "^MOVE": [100.0 + (i % 8) * 1.2 for i in range(140)],
            "CL=F": [70.0 + i * 0.25 for i in range(140)],
            "BZ=F": [74.0 + i * 0.28 for i in range(140)],
            "DX-Y.NYB": [94.0 + i * 0.06 for i in range(140)],
            "^TNX": [2.0 + i * 0.015 for i in range(140)],
        },
        index=index,
        dtype=float,
    )

    frames = build_risk_line_feature_frames(prices, zscore_window=26, percentile_window=52)

    assert set(frames) == {"SPY", "HYG", "LQD", "HYG/LQD", "^VIX", "^MOVE", "CL=F", "BZ=F", "DX-Y.NYB", "^TNX"}
    assert {"roc_1w", "roc_z_4w", "level_percentile", "adverse_persistence_4", "drawdown_and_roc_4w"}.issubset(frames["SPY"].columns)
    assert "drawdown_and_roc_4w" in frames["HYG"].columns
    assert "drawdown_and_roc_4w" in frames["LQD"].columns
    assert "level_and_roc_4w" in frames["HYG/LQD"].columns
    assert "level_and_roc_8w" in frames["HYG/LQD"].columns
    assert "level_and_roc_4w" in frames["^VIX"].columns
    assert "level_and_roc_8w" in frames["^VIX"].columns
    assert "level_and_roc_4w" in frames["^MOVE"].columns
    assert "level_and_roc_4w" in frames["CL=F"].columns
    assert "level_and_roc_4w" in frames["BZ=F"].columns
    assert "level_and_roc_4w" in frames["DX-Y.NYB"].columns
    assert "level_and_roc_4w" in frames["^TNX"].columns


def test_strict_missing_value_pct_change_differs_from_compatible_behavior():
    series = pd.Series([100.0, None, 110.0, 105.0, None, 120.0])

    compatible = series.ffill().pct_change(fill_method=None)
    strict_missing = series.pct_change(fill_method=None)

    assert not compatible.equals(strict_missing)


def test_feature_frame_with_missing_values_uses_compatible_roc_values_without_warning():
    prices = pd.DataFrame({"SPY": [100.0, None, 110.0, 105.0, None, 120.0]})
    compatible_roc = prices["SPY"].ffill().pct_change(fill_method=None)
    strict_roc = prices["SPY"].pct_change(fill_method=None)

    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        frame = build_risk_line_feature_frames(prices, zscore_window=2, percentile_window=2)["SPY"]

    pd.testing.assert_series_equal(frame["roc_1w"], compatible_roc, check_names=False)
    assert not frame["roc_1w"].equals(strict_roc)
