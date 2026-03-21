from __future__ import annotations

from typing import Any

import pandas as pd

from project.indicators import rate_of_change, ratio_series, rolling_zscore
from project.ticker_labels import ticker_label_ja


def build_credit_monitor(
    prices: pd.DataFrame,
    credit_map: dict[str, str],
    windows: dict[str, int],
    zscore_window: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for ticker in credit_map.values():
        if ticker not in prices.columns:
            continue
        rows.append(_monitor_row(prices[ticker], ticker, ticker_label_ja(ticker), windows, zscore_window))

    hyg = credit_map.get("HYG")
    lqd = credit_map.get("LQD")
    if hyg and lqd and hyg in prices.columns and lqd in prices.columns:
        ratio = ratio_series(prices[hyg], prices[lqd])
        if not ratio.empty:
            rows.append(_monitor_row(ratio, "HYG/LQD", "ハイイールド債/投資適格債 比率", windows, zscore_window))

    return rows


def _monitor_row(
    series: pd.Series,
    ticker: str,
    label_ja: str,
    windows: dict[str, int],
    zscore_window: int,
) -> dict[str, Any]:
    current = float(series.dropna().iloc[-1]) if not series.dropna().empty else float("nan")
    change_short = rate_of_change(series, windows["short"])
    change_medium = rate_of_change(series, windows["medium"])
    change_long = rate_of_change(series, windows["long"])
    zscore = rolling_zscore(series, zscore_window)

    return {
        "ticker": ticker,
        "ticker_name_ja": label_ja,
        "current": round(current, 4),
        "change_1w": round(change_short, 4),
        "change_4w": round(change_medium, 4),
        "change_12w": round(change_long, 4),
        "zscore": round(zscore, 4),
        "signal_label": _signal_label(ticker, change_short, change_medium, zscore),
    }


def _signal_label(ticker: str, change_short: float, change_medium: float, zscore: float) -> str:
    if ticker == "HYG/LQD":
        if _is_negative(zscore, threshold=-1.0) or _is_negative(change_medium, threshold=-0.02):
            return "信用収縮警戒"
        if _is_positive(zscore, threshold=1.0) and _is_positive(change_medium, threshold=0.02):
            return "信用改善"
        return "信用温度差を監視"

    if _is_negative(zscore, threshold=-1.0) or _is_negative(change_short, threshold=-0.015):
        return "弱含み"
    if _is_positive(zscore, threshold=1.0) and _is_positive(change_short, threshold=0.015):
        return "改善"
    return "中立"


def _is_negative(value: float, threshold: float) -> bool:
    return pd.notna(value) and value <= threshold


def _is_positive(value: float, threshold: float) -> bool:
    return pd.notna(value) and value >= threshold
