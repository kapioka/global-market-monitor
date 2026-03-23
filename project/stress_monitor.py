from __future__ import annotations

from typing import Any

import pandas as pd

from project.indicators import rate_of_change, ratio_series, rolling_zscore
from project.ticker_labels import ticker_label_ja


LEVEL_RANK = {"normal": 0, "warning": 1, "danger": 2, "extreme": 3}
LEVEL_LABELS = {
    "normal": "通常",
    "warning": "警戒ライン接近",
    "danger": "危険ライン到達",
    "extreme": "非常に危険ライン到達",
}

STRESS_INDICATOR_DEFAULTS = {
    "SPY": "SPY",
    "HYG": "HYG",
    "LQD": "LQD",
    "VIX": "^VIX",
    "MOVE": "^MOVE",
    "WTI": "CL=F",
    "Brent": "BZ=F",
    "DXY": "DX-Y.NYB",
    "US10Y": "^TNX",
}

STRESS_DEFINITIONS: dict[str, dict[str, Any]] = {
    "SPY": {"kind": "negative_change", "field": "change_1w", "thresholds": {"warning": -0.03, "danger": -0.05, "extreme": -0.08}, "weight": 1.15},
    "HYG": {"kind": "negative_change", "field": "change_1w", "thresholds": {"warning": -0.015, "danger": -0.03, "extreme": -0.05}, "weight": 1.05},
    "LQD": {"kind": "negative_change", "field": "change_4w", "thresholds": {"warning": -0.02, "danger": -0.04, "extreme": -0.06}, "weight": 0.85},
    "HYG/LQD": {"kind": "ratio_combo", "thresholds": {"warning": {"change_4w": -0.015, "zscore": -0.8}, "danger": {"change_4w": -0.025, "zscore": -1.2}, "extreme": {"change_4w": -0.04, "zscore": -1.8}}, "weight": 1.3},
    "^VIX": {"kind": "absolute_high", "thresholds": {"warning": 25.0, "danger": 30.0, "extreme": 35.0}, "weight": 1.2},
    "^MOVE": {"kind": "absolute_high", "thresholds": {"warning": 110.0, "danger": 120.0, "extreme": 135.0}, "weight": 1.2},
    "CL=F": {"kind": "absolute_high", "thresholds": {"warning": 100.0, "danger": 110.0, "extreme": 120.0}, "weight": 0.9},
    "BZ=F": {"kind": "absolute_high", "thresholds": {"warning": 105.0, "danger": 115.0, "extreme": 125.0}, "weight": 1.0},
    "DX-Y.NYB": {"kind": "absolute_high", "thresholds": {"warning": 99.0, "danger": 101.0, "extreme": 103.0}, "weight": 0.85},
    "^TNX": {"kind": "absolute_high", "thresholds": {"warning": 4.30, "danger": 4.45, "extreme": 4.60}, "weight": 1.05},
}


def default_risk_indicator_map(config: dict[str, Any]) -> dict[str, str]:
    indicator_map = dict(config.get("tickers", {}).get("risk_indicators", {}))
    for alias, ticker in STRESS_INDICATOR_DEFAULTS.items():
        indicator_map.setdefault(alias, ticker)
    return indicator_map


def build_stress_monitor(
    prices: pd.DataFrame,
    indicator_map: dict[str, str],
    windows: dict[str, int],
    zscore_window: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ticker in indicator_map.values():
        if ticker in seen or ticker not in prices.columns:
            continue
        seen.add(ticker)
        rows.append(_monitor_row(prices[ticker], ticker, ticker_label_ja(ticker), windows, zscore_window))

    hyg = indicator_map.get("HYG", "HYG")
    lqd = indicator_map.get("LQD", "LQD")
    if hyg in prices.columns and lqd in prices.columns:
        ratio = ratio_series(prices[hyg], prices[lqd])
        if not ratio.empty:
            rows.append(_monitor_row(ratio, "HYG/LQD", "ハイイールド債/投資適格債 比率", windows, zscore_window))

    order = {ticker: index for index, ticker in enumerate(STRESS_DEFINITIONS.keys())}
    rows.sort(key=lambda row: order.get(str(row.get("ticker", "")), 999))
    return rows


def _monitor_row(
    series: pd.Series,
    ticker: str,
    label_ja: str,
    windows: dict[str, int],
    zscore_window: int,
) -> dict[str, Any]:
    clean = series.dropna()
    current = float(clean.iloc[-1]) if not clean.empty else float("nan")
    change_short = rate_of_change(series, windows["short"])
    change_medium = rate_of_change(series, windows["medium"])
    change_long = rate_of_change(series, windows["long"])
    zscore = rolling_zscore(series, zscore_window)
    recent_values = [round(float(value), 4) for value in clean.tail(5).tolist()]
    stress_state = _stress_state_for_row(ticker, current, change_short, change_medium, zscore, recent_values)
    return {
        "ticker": ticker,
        "ticker_name_ja": label_ja,
        "current": round(current, 4),
        "change_1w": round(change_short, 4),
        "change_4w": round(change_medium, 4),
        "change_12w": round(change_long, 4),
        "zscore": round(zscore, 4),
        "recent_values": recent_values,
        "signal_label": stress_state["signal_label"],
        "line_level": stress_state["line_level"],
        "line_level_label": LEVEL_LABELS[stress_state["line_level"]],
        "line_reason": stress_state["line_reason"],
        "warning_line": stress_state["warning_line"],
        "danger_line": stress_state["danger_line"],
        "extreme_line": stress_state["extreme_line"],
        "recent_warning_hits": stress_state["recent_warning_hits"],
        "recent_danger_hits": stress_state["recent_danger_hits"],
        "recent_extreme_hits": stress_state["recent_extreme_hits"],
        "weight": stress_state["weight"],
        "pressure_score": round(stress_state["pressure_score"], 4),
        "health_score": round(1.0 - stress_state["pressure_score"], 4),
    }


def _stress_state_for_row(
    ticker: str,
    current: float,
    change_1w: float,
    change_4w: float,
    zscore: float,
    recent_values: list[float],
) -> dict[str, Any]:
    definition = STRESS_DEFINITIONS.get(ticker, {"kind": "neutral", "thresholds": {}, "weight": 1.0})
    kind = str(definition.get("kind", "neutral"))
    thresholds = definition.get("thresholds", {})
    if kind == "absolute_high":
        level = _absolute_level(current, thresholds)
        pressure = _absolute_pressure(current, thresholds)
        reason = f"現在値 {current:.2f} を基準ラインと比較した判定です。"
        signal = f"{ticker_label_ja(ticker)}は {LEVEL_LABELS[level]}"
    elif kind == "negative_change":
        field = str(definition.get("field", "change_1w"))
        value = change_1w if field == "change_1w" else change_4w
        level = _negative_level(value, thresholds)
        pressure = _negative_pressure(value, thresholds)
        reason = f"{field} の下落率 {value:.4f} を基準ラインと比較した判定です。"
        signal = f"{ticker_label_ja(ticker)}は {LEVEL_LABELS[level]}"
    elif kind == "ratio_combo":
        level = _ratio_level(change_4w, zscore, thresholds)
        pressure = max(_negative_pressure(change_4w, {key: value['change_4w'] for key, value in thresholds.items()}), _zscore_pressure(zscore, {key: value['zscore'] for key, value in thresholds.items()}))
        reason = f"4週変化率 {change_4w:.4f} と z スコア {zscore:.2f} を合わせた判定です。"
        signal = f"{ticker_label_ja(ticker)}は {LEVEL_LABELS[level]}"
    else:
        level = "normal"
        pressure = 0.0
        reason = "補助系列として記録のみ行っています。"
        signal = "補助系列"
    warning_line = _threshold_value_for_display(thresholds, "warning")
    danger_line = _threshold_value_for_display(thresholds, "danger")
    extreme_line = _threshold_value_for_display(thresholds, "extreme")
    return {
        "line_level": level,
        "signal_label": signal,
        "line_reason": reason,
        "warning_line": warning_line,
        "danger_line": danger_line,
        "extreme_line": extreme_line,
        "recent_warning_hits": _recent_hits(recent_values, warning_line),
        "recent_danger_hits": _recent_hits(recent_values, danger_line),
        "recent_extreme_hits": _recent_hits(recent_values, extreme_line),
        "weight": float(definition.get("weight", 1.0)),
        "pressure_score": min(max(float(pressure), 0.0), 1.0),
    }


def _absolute_level(value: float, thresholds: dict[str, float]) -> str:
    if pd.notna(value) and value >= thresholds.get("extreme", float("inf")):
        return "extreme"
    if pd.notna(value) and value >= thresholds.get("danger", float("inf")):
        return "danger"
    if pd.notna(value) and value >= thresholds.get("warning", float("inf")):
        return "warning"
    return "normal"


def _negative_level(value: float, thresholds: dict[str, float]) -> str:
    if pd.notna(value) and value <= thresholds.get("extreme", float("-inf")):
        return "extreme"
    if pd.notna(value) and value <= thresholds.get("danger", float("-inf")):
        return "danger"
    if pd.notna(value) and value <= thresholds.get("warning", float("-inf")):
        return "warning"
    return "normal"


def _ratio_level(change_4w: float, zscore: float, thresholds: dict[str, dict[str, float]]) -> str:
    for level in ("extreme", "danger", "warning"):
        bounds = thresholds.get(level, {})
        if pd.notna(change_4w) and change_4w <= bounds.get("change_4w", float("-inf")):
            return level
        if pd.notna(zscore) and zscore <= bounds.get("zscore", float("-inf")):
            return level
    return "normal"


def _absolute_pressure(value: float, thresholds: dict[str, float]) -> float:
    if not pd.notna(value):
        return 0.5
    warning = float(thresholds.get("warning", 1.0))
    danger = float(thresholds.get("danger", warning))
    extreme = float(thresholds.get("extreme", danger))
    if value < warning:
        return min(max((value / warning) * 0.33, 0.0), 0.33)
    if value < danger:
        width = max(danger - warning, 1e-9)
        return 0.33 + ((value - warning) / width) * 0.34
    if value < extreme:
        width = max(extreme - danger, 1e-9)
        return 0.67 + ((value - danger) / width) * 0.32
    return 1.0


def _negative_pressure(value: float, thresholds: dict[str, float]) -> float:
    if not pd.notna(value):
        return 0.5
    warning = abs(float(thresholds.get("warning", -0.01)))
    danger = abs(float(thresholds.get("danger", -0.02)))
    extreme = abs(float(thresholds.get("extreme", -0.03)))
    adverse = max(-float(value), 0.0)
    if adverse < warning:
        return min(max((adverse / warning) * 0.33, 0.0), 0.33)
    if adverse < danger:
        width = max(danger - warning, 1e-9)
        return 0.33 + ((adverse - warning) / width) * 0.34
    if adverse < extreme:
        width = max(extreme - danger, 1e-9)
        return 0.67 + ((adverse - danger) / width) * 0.32
    return 1.0


def _zscore_pressure(value: float, thresholds: dict[str, float]) -> float:
    if not pd.notna(value):
        return 0.5
    warning = abs(float(thresholds.get("warning", -0.8)))
    danger = abs(float(thresholds.get("danger", -1.2)))
    extreme = abs(float(thresholds.get("extreme", -1.8)))
    adverse = max(-float(value), 0.0)
    if adverse < warning:
        return min(max((adverse / warning) * 0.33, 0.0), 0.33)
    if adverse < danger:
        width = max(danger - warning, 1e-9)
        return 0.33 + ((adverse - warning) / width) * 0.34
    if adverse < extreme:
        width = max(extreme - danger, 1e-9)
        return 0.67 + ((adverse - danger) / width) * 0.32
    return 1.0


def _threshold_value_for_display(thresholds: Any, level: str) -> Any:
    value = thresholds.get(level) if isinstance(thresholds, dict) else None
    if isinstance(value, dict):
        return "/".join(f"{key}:{raw}" for key, raw in value.items())
    return value


def _recent_hits(values: list[float], threshold: Any) -> int:
    if not values or not isinstance(threshold, (int, float)):
        return 0
    return sum(1 for value in values if value >= float(threshold))
