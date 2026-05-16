from __future__ import annotations

import pandas as pd

from project.indicators import annualized_volatility, max_drawdown, momentum
from project.ticker_labels import ticker_label_ja


def compare_asset_classes(prices: pd.DataFrame, asset_map: dict[str, str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for label, ticker in asset_map.items():
        if ticker not in prices.columns:
            continue
        series = prices[ticker]
        returns = series.pct_change()
        rows.append(
            {
                "asset_class": label,
                "ticker": ticker,
                "ticker_name_ja": ticker_label_ja(ticker),
                "momentum_12w": round(momentum(series, 12), 4),
                "annualized_volatility": round(annualized_volatility(returns), 4),
                "max_drawdown": round(max_drawdown(series), 4),
            }
        )
    return sorted(rows, key=lambda row: row["momentum_12w"], reverse=True)
