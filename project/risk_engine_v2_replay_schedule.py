from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def canonical_weekly_prices(prices: pd.DataFrame, *, week_rule: str = "W-FRI") -> pd.DataFrame:
    clean = prices.copy()
    clean.index = pd.to_datetime(clean.index, errors="coerce").tz_localize(None)
    clean = clean[clean.index.notna()]
    clean = clean.sort_index()
    clean = clean[~clean.index.duplicated(keep="last")]
    numeric = clean.apply(pd.to_numeric, errors="coerce")
    weekly = numeric.resample(week_rule).last()
    return weekly.dropna(how="all")


def select_calendar_spaced_dates(candidates: Iterable[pd.Timestamp], *, stride_weeks: int) -> list[pd.Timestamp]:
    stride = max(1, int(stride_weeks))
    selected: list[pd.Timestamp] = []
    next_allowed: pd.Timestamp | None = None
    for candidate in sorted(pd.Timestamp(item).normalize() for item in candidates):
        if next_allowed is None or candidate >= next_allowed:
            selected.append(candidate)
            next_allowed = candidate + pd.Timedelta(weeks=stride)
    return selected


def limit_cases_across_period(dates: list[pd.Timestamp], max_cases: int | None) -> list[pd.Timestamp]:
    if max_cases is None or max_cases <= 0 or len(dates) <= max_cases:
        return dates
    if max_cases == 1:
        return [dates[0]]
    last_index = len(dates) - 1
    selected_indices = {round(index * last_index / (max_cases - 1)) for index in range(max_cases)}
    return [dates[index] for index in sorted(selected_indices)]
