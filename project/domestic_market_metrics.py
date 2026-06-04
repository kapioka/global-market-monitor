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


def build_domestic_market_metrics(
    prices: pd.DataFrame,
    *,
    acquisition_log: list[dict[str, Any]] | None = None,
    include_references: bool = True,
    zscore_window: int = 26,
) -> dict[str, Any]:
    acquisition_map = _acquisition_map(acquisition_log or [])
    symbols = list(TARGET_SYMBOLS)
    if include_references:
        symbols.extend(REFERENCE_SYMBOLS)
    rows = [_metric_row(prices, symbol, acquisition_map.get(symbol), zscore_window) for symbol in symbols]
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
) -> dict[str, Any]:
    source_status = str((acquisition or {}).get("status") or ("ok" if symbol in prices.columns else "missing"))
    source_kind = str((acquisition or {}).get("source") or (acquisition or {}).get("source_kind") or "price_series")
    is_sample = source_status == "sample_fallback" or source_kind == "sample"
    series = _clean_series(prices[symbol]) if symbol in prices.columns else pd.Series(dtype=float)
    limitations: list[str] = []
    if series.empty:
        limitations.append("missing_series")
    if len(series) <= 12:
        limitations.append("insufficient_history")

    current_value = _latest(series)
    change_1w = _change_percent(series, 1, limitations)
    change_4w = _change_percent(series, 4, limitations)
    change_12w = _change_percent(series, 12, limitations)
    momentum_12w = _safe_metric(momentum(series, 12))
    drawdown = _safe_metric(max_drawdown(series))
    zscore = _safe_metric(rolling_zscore(series, zscore_window))
    volatility = _safe_metric(annualized_volatility(series.pct_change(fill_method=None)))
    if zscore is None:
        limitations.append("insufficient_zscore_history")

    is_available = current_value is not None and source_status not in {"missing", "failed", "unavailable"}
    return {
        "symbol": symbol,
        "display_name": ticker_label_ja(symbol),
        "asset_group": DOMESTIC_METRIC_SYMBOLS[symbol],
        "source_status": source_status,
        "source_kind": source_kind,
        "latest_date": _latest_date(series),
        "current_value": current_value,
        "change_1w": change_1w,
        "change_4w": change_4w,
        "change_12w": change_12w,
        "momentum_12w": _percent(momentum_12w),
        "max_drawdown": _percent(drawdown),
        "zscore": _rounded(zscore),
        "trend_label": _trend_label(change_4w, change_12w),
        "volatility_label": _volatility_label(volatility),
        "data_quality": _data_quality(is_available, is_sample, limitations),
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


def _latest(series: pd.Series) -> float | None:
    if series.empty:
        return None
    return _rounded(float(series.iloc[-1]))


def _latest_date(series: pd.Series) -> str | None:
    if series.empty:
        return None
    value = series.index[-1]
    if hasattr(value, "date"):
        return value.date().isoformat()
    return str(value)


def _change_percent(series: pd.Series, window: int, limitations: list[str]) -> float | None:
    if len(series) <= window:
        if "insufficient_history" not in limitations:
            limitations.append("insufficient_history")
        return None
    previous = float(series.iloc[-(window + 1)])
    if previous == 0:
        limitations.append("zero_reference_value")
        return None
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
