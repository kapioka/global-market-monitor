from __future__ import annotations

import pandas as pd


def find_analogues(prices: pd.Series, max_results: int = 5) -> list[dict[str, object]]:
    clean = prices.dropna()
    if len(clean) < 80:
        return []

    returns = clean.pct_change().dropna()
    pattern = returns.tail(12)
    results: list[dict[str, object]] = []

    for end in range(24, len(returns) - 12):
        window = returns.iloc[end - 12 : end]
        similarity = float(pattern.corr(window))
        if pd.isna(similarity):
            continue
        forward_return = float(clean.iloc[end + 12] / clean.iloc[end] - 1.0)
        results.append(
            {
                "end_date": str(returns.index[end].date()),
                "similarity": round(similarity, 4),
                "forward_12w_return": round(forward_return, 4),
            }
        )

    return sorted(results, key=lambda row: row["similarity"], reverse=True)[:max_results]
