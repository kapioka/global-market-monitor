from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from project.indicators import ratio_series


@dataclass(frozen=True)
class RiskLabelConfig:
    warning_horizon_weeks: int = 4
    danger_horizon_weeks: int = 4
    extreme_horizon_weeks: int = 3
    warning_spy_drop: float = -0.04
    danger_spy_drop: float = -0.06
    extreme_spy_drop: float = -0.05
    warning_ratio_drop: float = -0.02
    danger_ratio_drop: float = -0.035
    extreme_ratio_drop: float = -0.03
    warning_vix_level: float = 30.0
    danger_vix_level: float = 35.0
    extreme_vix_level: float = 38.0
    extreme_min_trigger_count: int = 2


def build_risk_event_labels(prices: pd.DataFrame, config: RiskLabelConfig | None = None) -> pd.DataFrame:
    cfg = config or RiskLabelConfig()
    required = {"SPY", "HYG", "LQD", "^VIX"}
    available = required.intersection(prices.columns)
    if {"SPY", "HYG", "LQD", "^VIX"} - available:
        missing = sorted(required.difference(prices.columns))
        raise ValueError(f"prices is missing required columns: {', '.join(missing)}")

    spy = prices["SPY"].astype(float)
    vix = prices["^VIX"].astype(float)
    ratio = ratio_series(prices["HYG"].astype(float), prices["LQD"].astype(float)).reindex(prices.index)

    frame = pd.DataFrame(index=prices.index)
    frame["future_spy_min_return_4w"] = _future_min_return(spy, cfg.warning_horizon_weeks)
    frame["future_spy_min_return_3w"] = _future_min_return(spy, cfg.extreme_horizon_weeks)
    frame["future_ratio_min_return_4w"] = _future_min_return(ratio, cfg.warning_horizon_weeks)
    frame["future_ratio_min_return_3w"] = _future_min_return(ratio, cfg.extreme_horizon_weeks)
    frame["future_vix_max_4w"] = _future_max(vix, cfg.warning_horizon_weeks)
    frame["future_vix_max_3w"] = _future_max(vix, cfg.extreme_horizon_weeks)

    warning_lead = pd.concat(
        [
            _lead_to_min_return(spy, cfg.warning_horizon_weeks, cfg.warning_spy_drop),
            _lead_to_min_return(ratio, cfg.warning_horizon_weeks, cfg.warning_ratio_drop),
            _lead_to_max_level(vix, cfg.warning_horizon_weeks, cfg.warning_vix_level),
        ],
        axis=1,
    ).min(axis=1, skipna=True)
    danger_lead = pd.concat(
        [
            _lead_to_min_return(spy, cfg.danger_horizon_weeks, cfg.danger_spy_drop),
            _lead_to_min_return(ratio, cfg.danger_horizon_weeks, cfg.danger_ratio_drop),
            _lead_to_max_level(vix, cfg.danger_horizon_weeks, cfg.danger_vix_level),
        ],
        axis=1,
    ).min(axis=1, skipna=True)

    extreme_components = pd.concat(
        [
            _lead_to_min_return(spy, cfg.extreme_horizon_weeks, cfg.extreme_spy_drop),
            _lead_to_min_return(ratio, cfg.extreme_horizon_weeks, cfg.extreme_ratio_drop),
            _lead_to_max_level(vix, cfg.extreme_horizon_weeks, cfg.extreme_vix_level),
        ],
        axis=1,
    )
    extreme_components.columns = ["spy", "ratio", "vix"]
    extreme_trigger_count = extreme_components.notna().sum(axis=1)
    extreme_lead = _lead_for_trigger_count(extreme_components, cfg.extreme_min_trigger_count)

    frame["warning_target"] = warning_lead.notna()
    frame["danger_target"] = danger_lead.notna()
    frame["extreme_target"] = extreme_lead.notna()
    frame["warning_lead_weeks"] = warning_lead
    frame["danger_lead_weeks"] = danger_lead
    frame["extreme_lead_weeks"] = extreme_lead
    frame["extreme_trigger_count"] = extreme_trigger_count
    return frame


def _future_min_return(series: pd.Series, horizon: int) -> pd.Series:
    values = []
    for idx in range(len(series)):
        current = series.iloc[idx]
        future = series.iloc[idx + 1 : idx + horizon + 1].dropna()
        if pd.isna(current) or current == 0 or future.empty:
            values.append(float("nan"))
            continue
        values.append(float(future.min() / current - 1.0))
    return pd.Series(values, index=series.index, dtype=float)


def _future_max(series: pd.Series, horizon: int) -> pd.Series:
    values = []
    for idx in range(len(series)):
        future = series.iloc[idx + 1 : idx + horizon + 1].dropna()
        values.append(float(future.max()) if not future.empty else float("nan"))
    return pd.Series(values, index=series.index, dtype=float)


def _lead_to_min_return(series: pd.Series, horizon: int, threshold: float) -> pd.Series:
    values = []
    for idx in range(len(series)):
        current = series.iloc[idx]
        future = series.iloc[idx + 1 : idx + horizon + 1]
        if pd.isna(current) or current == 0 or future.dropna().empty:
            values.append(float("nan"))
            continue
        lead = float("nan")
        for step, future_value in enumerate(future, start=1):
            if pd.isna(future_value):
                continue
            if float(future_value / current - 1.0) <= threshold:
                lead = float(step)
                break
        values.append(lead)
    return pd.Series(values, index=series.index, dtype=float)


def _lead_to_max_level(series: pd.Series, horizon: int, threshold: float) -> pd.Series:
    values = []
    for idx in range(len(series)):
        future = series.iloc[idx + 1 : idx + horizon + 1]
        if future.dropna().empty:
            values.append(float("nan"))
            continue
        lead = float("nan")
        for step, future_value in enumerate(future, start=1):
            if pd.isna(future_value):
                continue
            if float(future_value) >= threshold:
                lead = float(step)
                break
        values.append(lead)
    return pd.Series(values, index=series.index, dtype=float)


def _lead_for_trigger_count(leads: pd.DataFrame, min_trigger_count: int) -> pd.Series:
    values: list[float] = []
    for _, row in leads.iterrows():
        valid = sorted(float(value) for value in row.dropna().tolist())
        if len(valid) < min_trigger_count:
            values.append(float("nan"))
            continue
        values.append(valid[min_trigger_count - 1])
    return pd.Series(values, index=leads.index, dtype=float)
