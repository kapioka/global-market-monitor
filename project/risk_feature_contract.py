from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd
from pandas.tseries.offsets import BDay

RETURN_WINDOWS = {"return_1w": 5, "return_4w": 20, "return_12w": 60}
VOLATILITY_INDEX_SYMBOLS = {"^VIX", "^MOVE"}


@dataclass(frozen=True)
class ComparisonObservation:
    window: str
    sessions: int
    target_comparison_date: str
    observation_date: str | None
    value: float | None
    return_value: float | None
    status: str
    limitation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "window": self.window,
            "sessions": self.sessions,
            "target_comparison_date": self.target_comparison_date,
            "observation_date": self.observation_date,
            "value": self.value,
            "return_value": self.return_value,
            "status": self.status,
            "limitation": self.limitation,
        }


@dataclass(frozen=True)
class RiskSeriesMetadata:
    symbol: str
    source_kind: str
    frequency: str
    price_type: str
    evaluation_date: str
    latest_observation_date: str | None
    age_calendar_days: int | None
    age_business_days: int | None
    freshness_status: str
    comparison_observation_dates: dict[str, str | None]
    history_length: int
    quality_flags: list[str] = field(default_factory=list)
    stage_eligible: bool = False
    corroborative_eligible: bool = False
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "source_kind": self.source_kind,
            "frequency": self.frequency,
            "price_type": self.price_type,
            "evaluation_date": self.evaluation_date,
            "latest_observation_date": self.latest_observation_date,
            "age_calendar_days": self.age_calendar_days,
            "age_business_days": self.age_business_days,
            "freshness_status": self.freshness_status,
            "comparison_observation_dates": self.comparison_observation_dates,
            "history_length": self.history_length,
            "quality_flags": self.quality_flags,
            "stage_eligible": self.stage_eligible,
            "corroborative_eligible": self.corroborative_eligible,
            "limitations": self.limitations,
        }


def build_point_in_time_feature_contract(
    series: pd.Series,
    *,
    symbol: str,
    evaluation_date: str | date | pd.Timestamp,
    source_kind: str,
    price_type: str,
    minimum_history: int = 61,
    freshness_limits_calendar_days: dict[str, int] | None = None,
) -> dict[str, Any]:
    clean = normalize_observation_series(series)
    eval_ts = _normalize_timestamp(evaluation_date)
    usable = clean[clean.index <= eval_ts]
    quality_flags: list[str] = []
    limitations: list[str] = []

    if len(clean) < len(series.dropna()):
        quality_flags.append("duplicate_dates_normalized")
    if clean.empty:
        metadata = RiskSeriesMetadata(
            symbol=symbol,
            source_kind=source_kind,
            frequency="unknown",
            price_type=price_type,
            evaluation_date=_date_text(eval_ts),
            latest_observation_date=None,
            age_calendar_days=None,
            age_business_days=None,
            freshness_status="unknown",
            comparison_observation_dates={name: None for name in RETURN_WINDOWS},
            history_length=0,
            quality_flags=["source_unavailable"],
            stage_eligible=False,
            corroborative_eligible=False,
            limitations=["no valid observations at or before evaluation date"],
        )
        return {"metadata": metadata.to_dict(), "features": {}, "comparisons": {}}

    if usable.empty:
        metadata = RiskSeriesMetadata(
            symbol=symbol,
            source_kind=source_kind,
            frequency=_infer_frequency(clean),
            price_type=price_type,
            evaluation_date=_date_text(eval_ts),
            latest_observation_date=None,
            age_calendar_days=None,
            age_business_days=None,
            freshness_status="unknown",
            comparison_observation_dates={name: None for name in RETURN_WINDOWS},
            history_length=0,
            quality_flags=["future_observation_excluded", "source_unavailable"],
            stage_eligible=False,
            corroborative_eligible=False,
            limitations=["all observations are after evaluation date"],
        )
        return {"metadata": metadata.to_dict(), "features": {}, "comparisons": {}}

    current_date = usable.index[-1]
    current_value = float(usable.iloc[-1])
    frequency = _infer_frequency(usable)
    age_calendar_days = int((eval_ts.date() - current_date.date()).days)
    age_business_days = _business_days_between(current_date, eval_ts)
    freshness_status = _freshness_status(frequency, age_calendar_days, freshness_limits_calendar_days)
    if freshness_status == "stale":
        quality_flags.append("stale")
        limitations.append(f"latest observation is {age_calendar_days} calendar days old")
    if len(usable) < minimum_history:
        quality_flags.append("insufficient_history")
        limitations.append(f"history_length {len(usable)} is below minimum_history {minimum_history}")
    if clean.index.max() > eval_ts:
        quality_flags.append("future_observation_excluded")
        limitations.append("observations after evaluation_date were excluded")
    if _has_suspicious_discontinuity(usable, symbol=symbol, price_type=price_type):
        quality_flags.append("suspicious_discontinuity")
        limitations.append("large one-period change detected; review split, roll, or data discontinuity")

    comparisons = {
        name: _comparison_for_window(usable, eval_ts, current_date, current_value, name, sessions)
        for name, sessions in RETURN_WINDOWS.items()
    }
    for comparison in comparisons.values():
        if comparison.status != "valid":
            flag = comparison.status
            if flag not in quality_flags:
                quality_flags.append(flag)
            if comparison.limitation:
                limitations.append(comparison.limitation)

    stage_eligible = not any(
        flag
        in {
            "source_unavailable",
            "stale",
            "insufficient_history",
            "same_observation_comparison",
            "comparison_unavailable",
            "suspicious_discontinuity",
        }
        for flag in quality_flags
    )
    corroborative_eligible = not any(flag in {"source_unavailable", "stale"} for flag in quality_flags)
    metadata = RiskSeriesMetadata(
        symbol=symbol,
        source_kind=source_kind,
        frequency=frequency,
        price_type=price_type,
        evaluation_date=_date_text(eval_ts),
        latest_observation_date=_date_text(current_date),
        age_calendar_days=age_calendar_days,
        age_business_days=age_business_days,
        freshness_status=freshness_status,
        comparison_observation_dates={name: comparison.observation_date for name, comparison in comparisons.items()},
        history_length=len(usable),
        quality_flags=quality_flags or ["valid"],
        stage_eligible=stage_eligible,
        corroborative_eligible=corroborative_eligible,
        limitations=limitations,
    )
    features = {
        "current": current_value,
        **{name: comparison.return_value for name, comparison in comparisons.items()},
        "drawdown_13w": _drawdown_as_of(usable, current_date, current_value, 65),
        "level_zscore": _zscore(usable),
        "level_robust_zscore": _robust_zscore(usable),
    }
    return {
        "metadata": metadata.to_dict(),
        "features": features,
        "comparisons": {name: comparison.to_dict() for name, comparison in comparisons.items()},
    }


def normalize_observation_series(series: pd.Series) -> pd.Series:
    if series.empty:
        empty_index = pd.to_datetime(series.index, utc=True, errors="coerce").tz_convert(None).normalize()
        empty_index = empty_index[empty_index.notna()]
        return pd.Series(index=empty_index, dtype=float)
    normalized = series.copy()
    normalized.index = pd.to_datetime(normalized.index, utc=True, errors="coerce").tz_convert(None).normalize()
    normalized = normalized[normalized.index.notna()]
    normalized = pd.to_numeric(normalized, errors="coerce").dropna()
    normalized = normalized.sort_index()
    normalized = normalized[~normalized.index.duplicated(keep="last")]
    return normalized.astype(float)


def _comparison_for_window(
    usable: pd.Series,
    evaluation_date: pd.Timestamp,
    current_date: pd.Timestamp,
    current_value: float,
    window: str,
    sessions: int,
) -> ComparisonObservation:
    target_comparison = (evaluation_date - BDay(sessions)).normalize()
    candidates = usable[usable.index <= target_comparison]
    if candidates.empty:
        return ComparisonObservation(
            window=window,
            sessions=sessions,
            target_comparison_date=_date_text(target_comparison),
            observation_date=None,
            value=None,
            return_value=None,
            status="comparison_unavailable",
            limitation=f"{window} comparison unavailable before {target_comparison.date()}",
        )
    comparison_date = candidates.index[-1]
    comparison_value = float(candidates.iloc[-1])
    if comparison_date == current_date:
        return ComparisonObservation(
            window=window,
            sessions=sessions,
            target_comparison_date=_date_text(target_comparison),
            observation_date=_date_text(comparison_date),
            value=comparison_value,
            return_value=None,
            status="same_observation_comparison",
            limitation=f"{window} would compare {current_date.date()} to itself",
        )
    if comparison_value == 0:
        return ComparisonObservation(
            window=window,
            sessions=sessions,
            target_comparison_date=_date_text(target_comparison),
            observation_date=_date_text(comparison_date),
            value=comparison_value,
            return_value=None,
            status="comparison_unavailable",
            limitation=f"{window} comparison value is zero",
        )
    return ComparisonObservation(
        window=window,
        sessions=sessions,
        target_comparison_date=_date_text(target_comparison),
        observation_date=_date_text(comparison_date),
        value=comparison_value,
        return_value=(current_value / comparison_value) - 1.0,
        status="valid",
    )


def _infer_frequency(series: pd.Series) -> str:
    if len(series) < 2:
        return "unknown"
    gaps = series.index.to_series().diff().dropna().dt.days
    median_gap = float(gaps.median())
    if median_gap <= 4:
        return "daily"
    if median_gap <= 10:
        return "weekly"
    if median_gap <= 40:
        return "monthly"
    return "irregular"


def _freshness_status(
    frequency: str,
    age_calendar_days: int,
    freshness_limits_calendar_days: dict[str, int] | None,
) -> str:
    limits = {"daily": 5, "weekly": 14, "monthly": 45, "irregular": 14, "unknown": 14}
    if freshness_limits_calendar_days:
        limits.update(freshness_limits_calendar_days)
    return "fresh" if age_calendar_days <= int(limits.get(frequency, 14)) else "stale"


def _business_days_between(start: pd.Timestamp, end: pd.Timestamp) -> int:
    if end.normalize() <= start.normalize():
        return 0
    return len(pd.bdate_range(start.normalize() + BDay(1), end.normalize()))


def _drawdown_as_of(series: pd.Series, current_date: pd.Timestamp, current_value: float, sessions: int) -> float | None:
    start = (current_date - BDay(sessions)).normalize()
    window = series[(series.index >= start) & (series.index <= current_date)]
    if window.empty:
        return None
    peak = float(window.max())
    if peak == 0:
        return None
    return (current_value / peak) - 1.0


def _zscore(series: pd.Series) -> float | None:
    if len(series) < 3:
        return None
    std = float(series.std(ddof=0))
    if std == 0:
        return 0.0
    return (float(series.iloc[-1]) - float(series.mean())) / std


def _robust_zscore(series: pd.Series) -> float | None:
    if len(series) < 3:
        return None
    median = float(series.median())
    mad = float((series - median).abs().median())
    if mad == 0:
        return 0.0
    return 0.6745 * (float(series.iloc[-1]) - median) / mad


def _has_suspicious_discontinuity(
    series: pd.Series,
    *,
    symbol: str | None = None,
    price_type: str | None = None,
) -> bool:
    # Large one-period moves are intrinsic to volatility indices and are the
    # signal being measured, not evidence of a split-like data discontinuity.
    if price_type == "index" and symbol in VOLATILITY_INDEX_SYMBOLS:
        return False
    returns = series.pct_change(fill_method=None).replace([float("inf"), float("-inf")], pd.NA).dropna()
    if returns.empty:
        return False
    return bool((returns.abs() >= 0.45).any())


def _normalize_timestamp(value: str | date | pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(value).tz_localize(None).normalize()


def _date_text(value: pd.Timestamp) -> str:
    return value.date().isoformat()
