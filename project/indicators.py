from __future__ import annotations

import math

import numpy as np
import pandas as pd


def annualized_volatility(returns: pd.Series, periods_per_year: int = 52) -> float:
    clean = returns.dropna()
    if clean.empty:
        return float("nan")
    return float(clean.std(ddof=0) * math.sqrt(periods_per_year))


def drawdown_series(prices: pd.Series) -> pd.Series:
    peak = prices.cummax()
    return prices / peak - 1.0


def max_drawdown(prices: pd.Series) -> float:
    drawdowns = drawdown_series(prices).dropna()
    if drawdowns.empty:
        return float("nan")
    return float(drawdowns.min())


def relative_strength_ratio(base: pd.Series, benchmark: pd.Series, window: int = 12) -> float:
    aligned = pd.concat([base, benchmark], axis=1).dropna()
    if len(aligned) <= window:
        return float("nan")
    ratio = aligned.iloc[:, 0] / aligned.iloc[:, 1]
    return float(ratio.iloc[-1] / ratio.iloc[-window] - 1.0)


def atr_from_closes(prices: pd.Series, window: int = 14) -> float:
    clean = prices.dropna()
    if len(clean) <= window:
        return float("nan")
    tr = clean.diff().abs()
    return float(tr.rolling(window).mean().iloc[-1])


def adx_from_closes(prices: pd.Series, window: int = 14) -> float:
    clean = prices.dropna()
    if len(clean) <= window + 2:
        return float("nan")
    diff = clean.diff()
    plus_dm = diff.clip(lower=0)
    minus_dm = (-diff).clip(lower=0)
    tr = clean.diff().abs().rolling(window).sum().replace(0, np.nan)
    plus_di = 100 * plus_dm.rolling(window).sum() / tr
    minus_di = 100 * minus_dm.rolling(window).sum() / tr
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
    return float(dx.rolling(window).mean().iloc[-1])


def momentum(prices: pd.Series, window: int = 12) -> float:
    clean = prices.dropna()
    if len(clean) <= window:
        return float("nan")
    return float(clean.iloc[-1] / clean.iloc[-window] - 1.0)


def volatility_compression(returns: pd.Series, short_window: int = 4, long_window: int = 26) -> float:
    clean = returns.dropna()
    if len(clean) < long_window:
        return float("nan")
    short_vol = clean.tail(short_window).std(ddof=0)
    long_vol = clean.tail(long_window).std(ddof=0)
    if long_vol == 0:
        return float("nan")
    return float(short_vol / long_vol)


def ratio_series(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    aligned = pd.concat([numerator, denominator], axis=1).dropna()
    if aligned.empty:
        return pd.Series(dtype=float)
    ratio = aligned.iloc[:, 0] / aligned.iloc[:, 1].replace(0, np.nan)
    return ratio.dropna()


def rate_of_change(prices: pd.Series, window: int) -> float:
    clean = prices.dropna()
    if len(clean) <= window or window <= 0:
        return float("nan")
    return float(clean.iloc[-1] / clean.iloc[-(window + 1)] - 1.0)


def rolling_rate_of_change_zscore(prices: pd.Series, change_window: int, zscore_window: int) -> float:
    clean = prices.dropna()
    if len(clean) <= change_window or change_window <= 0:
        return float("nan")
    changes = clean.pct_change(periods=change_window).dropna()
    return rolling_zscore(changes, zscore_window)


def rolling_zscore(prices: pd.Series, window: int) -> float:
    clean = prices.dropna()
    if len(clean) < window or window <= 1:
        return float("nan")
    sample = clean.iloc[-window:]
    mean = sample.mean()
    std = sample.std(ddof=0)
    if std == 0 or np.isnan(std):
        return float("nan")
    return float((sample.iloc[-1] - mean) / std)
