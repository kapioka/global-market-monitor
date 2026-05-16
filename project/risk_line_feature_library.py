from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from project.indicators import ratio_series


@dataclass(frozen=True)
class IndicatorModelSpec:
    ticker: str
    family: str
    adverse_direction: str


MODEL_SPECS: dict[str, IndicatorModelSpec] = {
    "SPY": IndicatorModelSpec(ticker="SPY", family="price_shock", adverse_direction="lower"),
    "HYG": IndicatorModelSpec(ticker="HYG", family="price_shock", adverse_direction="lower"),
    "LQD": IndicatorModelSpec(ticker="LQD", family="price_shock", adverse_direction="lower"),
    "HYG/LQD": IndicatorModelSpec(ticker="HYG/LQD", family="credit_spread", adverse_direction="lower"),
    "^VIX": IndicatorModelSpec(ticker="^VIX", family="volatility_shock", adverse_direction="higher"),
    "^MOVE": IndicatorModelSpec(ticker="^MOVE", family="volatility_shock", adverse_direction="higher"),
    "CL=F": IndicatorModelSpec(ticker="CL=F", family="commodity_shock", adverse_direction="higher"),
    "BZ=F": IndicatorModelSpec(ticker="BZ=F", family="commodity_shock", adverse_direction="higher"),
    "DX-Y.NYB": IndicatorModelSpec(ticker="DX-Y.NYB", family="macro_level_shift", adverse_direction="higher"),
    "^TNX": IndicatorModelSpec(ticker="^TNX", family="macro_level_shift", adverse_direction="higher"),
}


def build_risk_line_feature_frames(
    prices: pd.DataFrame,
    zscore_window: int = 52,
    percentile_window: int = 104,
) -> dict[str, pd.DataFrame]:
    prepared = _prepare_series_map(prices)
    frames: dict[str, pd.DataFrame] = {}
    for ticker, spec in MODEL_SPECS.items():
        series = prepared.get(ticker)
        if series is None or series.dropna().empty:
            continue
        frames[ticker] = _build_feature_frame(series, spec, zscore_window=zscore_window, percentile_window=percentile_window)
    return frames


def _prepare_series_map(prices: pd.DataFrame) -> dict[str, pd.Series]:
    prepared: dict[str, pd.Series] = {}
    for ticker in {spec.ticker for spec in MODEL_SPECS.values() if spec.ticker != "HYG/LQD"}:
        if ticker in prices.columns:
            prepared[ticker] = prices[ticker].astype(float)
    if "HYG" in prices.columns and "LQD" in prices.columns:
        ratio = ratio_series(prices["HYG"].astype(float), prices["LQD"].astype(float))
        if not ratio.empty:
            prepared["HYG/LQD"] = ratio
    return prepared


def _build_feature_frame(
    series: pd.Series,
    spec: IndicatorModelSpec,
    zscore_window: int,
    percentile_window: int,
) -> pd.DataFrame:
    clean = series.astype(float)
    frame = pd.DataFrame(index=clean.index)
    frame["current"] = clean
    frame["family"] = spec.family
    frame["adverse_direction"] = spec.adverse_direction

    for window in (1, 2, 4, 8):
        returns = clean.pct_change(periods=window)
        frame[f"roc_{window}w"] = returns
        frame[f"roc_z_{window}w"] = returns.rolling(zscore_window).apply(_zscore_last, raw=False)

    frame["level_zscore"] = clean.rolling(zscore_window).apply(_zscore_last, raw=False)
    frame["level_percentile"] = clean.rolling(percentile_window).apply(_percentile_last, raw=False)
    frame["adverse_persistence_4"] = _adverse_persistence(clean, spec.adverse_direction, lookback=4)
    frame["adverse_persistence_8"] = _adverse_persistence(clean, spec.adverse_direction, lookback=8)

    if spec.family == "price_shock":
        frame["drawdown_13w"] = _rolling_drawdown(clean, lookback=13)
        frame["drawdown_zscore"] = frame["drawdown_13w"].rolling(zscore_window).apply(_zscore_last, raw=False)
        frame["drawdown_and_roc_4w"] = _combine_low_side(frame["drawdown_zscore"], frame["roc_z_4w"])
        frame["level_and_roc_8w"] = _combine_low_side(frame["level_zscore"], frame["roc_z_8w"])
    elif spec.family == "credit_spread":
        frame["level_and_roc_4w"] = _combine_low_side(frame["level_zscore"], frame["roc_z_4w"])
        frame["level_and_roc_8w"] = _combine_low_side(frame["level_zscore"], frame["roc_z_8w"])
    elif spec.family in {"volatility_shock", "macro_level_shift", "commodity_shock"}:
        frame["level_and_roc_4w"] = _combine_high_side(frame["level_percentile"], frame["roc_z_4w"])
        frame["level_and_roc_8w"] = _combine_high_side(frame["level_percentile"], frame["roc_z_8w"])

    return frame.dropna(how="all")


def _rolling_drawdown(series: pd.Series, lookback: int) -> pd.Series:
    rolling_peak = series.rolling(lookback, min_periods=lookback).max()
    return series / rolling_peak - 1.0


def _adverse_persistence(series: pd.Series, adverse_direction: str, lookback: int) -> pd.Series:
    changes = series.pct_change()
    if adverse_direction == "higher":
        adverse = (changes > 0).astype(float)
    else:
        adverse = (changes < 0).astype(float)
    return adverse.rolling(lookback, min_periods=lookback).sum()


def _combine_high_side(level_percentile: pd.Series, roc_z: pd.Series) -> pd.Series:
    return pd.concat([level_percentile, _positive_unit_scale(roc_z)], axis=1).max(axis=1)


def _combine_low_side(level_z: pd.Series, roc_z: pd.Series) -> pd.Series:
    low_level = _negative_unit_scale(level_z)
    low_roc = _negative_unit_scale(roc_z)
    return pd.concat([low_level, low_roc], axis=1).max(axis=1)


def _positive_unit_scale(series: pd.Series) -> pd.Series:
    return series.clip(lower=0.0).div(3.0).clip(lower=0.0, upper=1.0)


def _negative_unit_scale(series: pd.Series) -> pd.Series:
    return series.mul(-1.0).clip(lower=0.0).div(3.0).clip(lower=0.0, upper=1.0)


def _zscore_last(window: pd.Series) -> float:
    clean = window.dropna()
    if len(clean) < 2:
        return float("nan")
    std = clean.std(ddof=0)
    if std == 0 or np.isnan(std):
        return float("nan")
    return float((clean.iloc[-1] - clean.mean()) / std)


def _percentile_last(window: pd.Series) -> float:
    clean = window.dropna()
    if len(clean) < 2:
        return float("nan")
    return float(clean.rank(method="average", pct=True).iloc[-1])
