from __future__ import annotations

from typing import Any

import pandas as pd

from project.indicators import rate_of_change, rolling_zscore
from project.ticker_labels import ticker_label_ja


def build_inflation_monitor(
    prices: pd.DataFrame,
    inflation_map: dict[str, str],
    windows: dict[str, int],
    zscore_window: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ticker in inflation_map.values():
        if ticker not in prices.columns:
            continue
        rows.append(_monitor_row(prices[ticker], ticker, ticker_label_ja(ticker), windows, zscore_window))
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
    if ticker == "CL=F":
        if _is_positive(zscore, 1.0) and _is_positive(change_medium, 0.05):
            return "インフレ圧力上昇"
        if _is_negative(change_medium, -0.05):
            return "インフレ圧力鈍化"
    if ticker in {"ZW=F", "ZC=F"}:
        if _is_positive(zscore, 0.9) and _is_positive(change_medium, 0.04):
            return "食品価格上昇圧力"
        if _is_negative(change_medium, -0.04):
            return "食品価格圧力鈍化"
    if ticker == "DX-Y.NYB":
        if _is_positive(zscore, 1.0) and _is_positive(change_medium, 0.02):
            return "ドル高進行"
    if ticker == "GC=F":
        if _is_positive(zscore, 1.0) and _is_positive(change_short, 0.02):
            return "安全資産選好"
    if ticker == "FRED:MORTGAGE30US":
        if _is_positive(zscore, 0.8) and _is_positive(change_medium, 0.015):
            return "住宅ローン負担上昇"
        if _is_negative(change_medium, -0.015):
            return "住宅ローン負担鈍化"
    if ticker == "^TNX":
        if _is_positive(zscore, 0.8) and _is_positive(change_medium, 0.03):
            return "住宅ローン負担上昇"
        if _is_negative(change_medium, -0.03):
            return "住宅ローン負担鈍化"
    return "中立"


def _is_positive(value: float, threshold: float) -> bool:
    return pd.notna(value) and value >= threshold


def _is_negative(value: float, threshold: float) -> bool:
    return pd.notna(value) and value <= threshold
