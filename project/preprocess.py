from __future__ import annotations

import pandas as pd


def preprocess_prices(prices: pd.DataFrame, min_history_points: int) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    cleaned = prices.sort_index().ffill()
    enough_history = cleaned.count() >= min_history_points
    dropped = enough_history[~enough_history].index.tolist()
    if dropped:
        warnings.append("Dropped short-history tickers: " + ", ".join(dropped))
        cleaned = cleaned.loc[:, enough_history]
    return cleaned, warnings


def compute_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change().replace([float("inf"), float("-inf")], pd.NA)
