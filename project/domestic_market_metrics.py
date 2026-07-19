from __future__ import annotations

from typing import Any

import pandas as pd

from project.indicators import annualized_volatility, max_drawdown, momentum, rolling_zscore
from project.ticker_labels import ticker_label_ja

DOMESTIC_METRIC_SYMBOLS: dict[str, str] = {
    "1306.T": "jp_equity",
    "1321.T": "jp_equity",
    "EWJ": "jp_equity",
    "2510.T": "jpy_bond",
    "1343.T": "jp_reit",
    "1540.T": "gold_jpy",
    "USDJPY=X": "fx",
    "EURJPY=X": "fx",
    "AGG": "foreign_bond",
    "TIP": "foreign_bond",
    "LQD": "foreign_bond",
    "HYG": "foreign_bond",
    "GLD": "gold_usd",
    "GC=F": "gold_usd",
}

TARGET_SYMBOLS = ("1306.T", "1321.T", "EWJ", "2510.T", "1343.T", "1540.T", "USDJPY=X", "EURJPY=X")
REFERENCE_SYMBOLS = ("AGG", "TIP", "LQD", "HYG", "GLD", "GC=F")
DISCONTINUITY_MOVE_THRESHOLD = 0.50


def build_domestic_market_metrics(
    prices: pd.DataFrame,
    *,
    acquisition_log: list[dict[str, Any]] | None = None,
    include_references: bool = True,
    zscore_window: int = 26,
    data_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    acquisition_map = _acquisition_map(acquisition_log or [])
    symbols = list(TARGET_SYMBOLS)
    if include_references:
        symbols.extend(REFERENCE_SYMBOLS)
    rows = [_metric_row(prices, symbol, acquisition_map.get(symbol), zscore_window, data_provenance or {}) for symbol in symbols]
    return {
        "title": "国内市場メトリクス",
        "summary": "国内ETF・為替系列の価格メトリクスを表示専用で整理します。",
        "affects_final_action": False,
        "affects_buy_readiness_score": False,
        "metrics": rows,
        "by_symbol": {row["symbol"]: row for row in rows},
    }


def _metric_row(
    prices: pd.DataFrame,
    symbol: str,
    acquisition: dict[str, Any] | None,
    zscore_window: int,
    data_provenance: dict[str, Any],
) -> dict[str, Any]:
    source_status = str((acquisition or {}).get("status") or ("ok" if symbol in prices.columns else "missing"))
    source_kind = str(
        (acquisition or {}).get("source")
        or (acquisition or {}).get("source_kind")
        or data_provenance.get("source_kind")
        or "price_series"
    )
    is_sample = source_status == "sample_fallback" or source_kind == "sample"
    series = _clean_series(prices[symbol]) if symbol in prices.columns else pd.Series(dtype=float)
    limitations: list[str] = []
    if series.empty:
        limitations.append("missing_series")
    if len(series) <= 12:
        limitations.append("insufficient_history")
    suspicious_discontinuity = _has_suspicious_discontinuity(series)
    if suspicious_discontinuity:
        limitations.append("split_or_discontinuity_suspected")

    current_value = _latest(series)
    comparison_windows: dict[str, Any] = {}
    change_1w = _change_percent(series, 1, limitations, comparison_windows, "change_1w")
    change_4w = _change_percent(series, 4, limitations, comparison_windows, "change_4w")
    change_12w = _change_percent(series, 12, limitations, comparison_windows, "change_12w")
    momentum_12w = _safe_metric(momentum(series, 12))
    drawdown_12w = _safe_metric(max_drawdown(series.tail(13)))
    drawdown_26w = _safe_metric(max_drawdown(series.tail(27)))
    drawdown_full = _safe_metric(max_drawdown(series))
    zscore = _safe_metric(rolling_zscore(series, zscore_window))
    volatility = _safe_metric(annualized_volatility(series.pct_change(fill_method=None)))
    if zscore is None:
        limitations.append("insufficient_zscore_history")
    if suspicious_discontinuity:
        momentum_12w = None
        drawdown_12w = None
        drawdown_26w = None
        zscore = None

    is_available = current_value is not None and source_status not in {"missing", "failed", "unavailable"}
    latest_date = _latest_date(series)
    return {
        "symbol": symbol,
        "display_name": ticker_label_ja(symbol),
        "asset_group": DOMESTIC_METRIC_SYMBOLS[symbol],
        "source_status": source_status,
        "source_kind": source_kind,
        "evaluation_date": data_provenance.get("evaluation_date"),
        "latest_date": latest_date,
        "latest_observation_date": latest_date,
        "age_business_days": data_provenance.get("age_business_days"),
        "freshness_status": data_provenance.get("freshness_status"),
        "stale_reason": data_provenance.get("stale_reason"),
        "live_fetch_performed": data_provenance.get("live_fetch_performed"),
        "current_value": current_value,
        "change_1w": change_1w,
        "change_4w": change_4w,
        "change_12w": change_12w,
        "comparison_windows": comparison_windows,
        "momentum_12w": _percent(momentum_12w),
        "max_drawdown": _percent(drawdown_12w),
        "max_drawdown_12w": _percent(drawdown_12w),
        "max_drawdown_26w": _percent(drawdown_26w),
        "max_drawdown_full": _percent(drawdown_full),
        "zscore": _rounded(zscore),
        "trend_label": "unknown" if suspicious_discontinuity else _trend_label(change_4w, change_12w),
        "volatility_label": _volatility_label(volatility),
        "data_quality": _data_quality(is_available, is_sample, limitations),
        "risk_signal_allowed": is_available and not suspicious_discontinuity,
        "stage_eligible": is_available and not suspicious_discontinuity and data_provenance.get("freshness_status") != "stale",
        "is_sample": is_sample,
        "is_partial": source_status in {"partial", "sample_fallback"} or bool(limitations),
        "is_available": is_available,
        "limitations": list(dict.fromkeys(limitations)),
    }


def _acquisition_map(acquisition_log: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for row in acquisition_log:
        for key in ("used_ticker", "requested_ticker"):
            symbol = str(row.get(key) or "")
            if symbol and symbol not in mapped:
                mapped[symbol] = row
    return mapped


def _clean_series(series: pd.Series) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return clean.astype(float)


def _has_suspicious_discontinuity(series: pd.Series) -> bool:
    if len(series) < 2:
        return False
    returns = series.pct_change(fill_method=None).dropna()
    return bool((returns.abs() > DISCONTINUITY_MOVE_THRESHOLD).any())


def _latest(series: pd.Series) -> float | None:
    if series.empty:
        return None
    return _rounded(float(series.iloc[-1]))


def _latest_date(series: pd.Series) -> str | None:
    if series.empty:
        return None
    return _date_to_string(series.index[-1])


def _date_to_string(value: Any) -> str:
    if hasattr(value, "date"):
        return value.date().isoformat()
    return str(value)


def _change_percent(
    series: pd.Series,
    window: int,
    limitations: list[str],
    comparison_windows: dict[str, Any],
    label: str,
) -> float | None:
    if len(series) <= window:
        if "insufficient_history" not in limitations:
            limitations.append("insufficient_history")
        comparison_windows[label] = {
            "window_observations": window,
            "latest_observation_date": _latest_date(series),
            "comparison_observation_date": None,
            "comparison_value": None,
            "comparison_available": False,
            "reason": "insufficient_history",
        }
        return None
    previous_index = series.index[-(window + 1)]
    previous = float(series.iloc[-(window + 1)])
    if previous == 0:
        limitations.append("zero_reference_value")
        comparison_windows[label] = {
            "window_observations": window,
            "latest_observation_date": _latest_date(series),
            "comparison_observation_date": _date_to_string(previous_index),
            "comparison_value": _rounded(previous),
            "comparison_available": False,
            "reason": "zero_reference_value",
        }
        return None
    comparison_windows[label] = {
        "window_observations": window,
        "latest_observation_date": _latest_date(series),
        "comparison_observation_date": _date_to_string(previous_index),
        "comparison_value": _rounded(previous),
        "comparison_available": True,
    }
    return _rounded((float(series.iloc[-1]) / previous - 1.0) * 100.0)


def _safe_metric(value: float) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _percent(value: float | None) -> float | None:
    if value is None:
        return None
    return _rounded(value * 100.0)


def _rounded(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)


def _trend_label(change_4w: float | None, change_12w: float | None) -> str:
    value = change_12w if change_12w is not None else change_4w
    if value is None:
        return "unknown"
    if value >= 2.0:
        return "rising"
    if value <= -8.0:
        return "falling"
    if value < -2.0:
        return "weakening"
    return "flat"


def _volatility_label(volatility: float | None) -> str:
    if volatility is None:
        return "unknown"
    if volatility < 0.08:
        return "low"
    if volatility > 0.25:
        return "elevated"
    return "normal"


def _data_quality(is_available: bool, is_sample: bool, limitations: list[str]) -> str:
    if not is_available:
        return "unavailable"
    if is_sample:
        return "sample"
    if limitations:
        return "partial"
    return "ok"
