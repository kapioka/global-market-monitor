from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from project.risk_line_threshold_store import DEFAULT_ACTIVE_DEFINITIONS, load_threshold_definitions
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

STRESS_DEFINITIONS: dict[str, dict[str, Any]] = DEFAULT_ACTIVE_DEFINITIONS
MODEL_REGISTRY_PATH = Path(__file__).resolve().parent / "reports" / "risk_line_model_registry.json"


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
    threshold_definitions: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    definitions = threshold_definitions or load_threshold_definitions()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ticker in indicator_map.values():
        if ticker in seen or ticker not in prices.columns:
            continue
        seen.add(ticker)
        rows.append(_monitor_row(prices[ticker], ticker, ticker_label_ja(ticker), windows, zscore_window, definitions))

    hyg = indicator_map.get("HYG", "HYG")
    lqd = indicator_map.get("LQD", "LQD")
    if hyg in prices.columns and lqd in prices.columns:
        ratio = prices[hyg].astype(float) / prices[lqd].astype(float)
        ratio = ratio.replace([float("inf"), float("-inf")], pd.NA).dropna()
        if not ratio.empty:
            rows.append(_monitor_row(ratio, "HYG/LQD", "ハイイールド債/投資適格債 比率", windows, zscore_window, definitions))

    order = {ticker: index for index, ticker in enumerate(definitions.keys())}
    rows.sort(key=lambda row: order.get(str(row.get("ticker", "")), 999))
    return rows


def _monitor_row(
    series: pd.Series,
    ticker: str,
    label_ja: str,
    windows: dict[str, int],
    zscore_window: int,
    definitions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    clean = series.dropna().astype(float)
    current = float(clean.iloc[-1]) if not clean.empty else float("nan")
    features = _build_feature_values(clean, windows, zscore_window)
    stress_state = _stress_state_for_row(ticker, features, definitions)
    return {
        "ticker": ticker,
        "ticker_name_ja": label_ja,
        "current": round(current, 4),
        "change_1w": round(float(features["change_1w"]), 4),
        "change_4w": round(float(features["change_4w"]), 4),
        "change_12w": round(float(features["change_12w"]), 4),
        "zscore": round(float(features["level_zscore"]), 4),
        "recent_values": [round(float(value), 4) for value in clean.tail(5).tolist()],
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


def _build_feature_values(series: pd.Series, windows: dict[str, int], zscore_window: int) -> dict[str, Any]:
    percentile_window = max(zscore_window * 2, 26)
    current = float(series.iloc[-1]) if not series.empty else float("nan")
    feature_series = {
        "current": series.astype(float),
        "change_1w": series.pct_change(periods=windows["short"]),
        "change_4w": series.pct_change(periods=windows["medium"]),
        "change_12w": series.pct_change(periods=windows["long"]),
        "level_zscore": _rolling_zscore_series(series, zscore_window),
        "level_percentile": _rolling_percentile_series(series, percentile_window),
        "drawdown_13w": _drawdown_series(series, 13),
        "roc_1w": series.pct_change(periods=1),
        "roc_2w": series.pct_change(periods=2),
        "roc_4w": series.pct_change(periods=4),
        "roc_8w": series.pct_change(periods=8),
    }
    feature_series["roc_z_1w"] = _rolling_zscore_series(feature_series["roc_1w"].dropna(), zscore_window).reindex(series.index)
    feature_series["roc_z_2w"] = _rolling_zscore_series(feature_series["roc_2w"].dropna(), zscore_window).reindex(series.index)
    feature_series["roc_z_4w"] = _rolling_zscore_series(feature_series["roc_4w"].dropna(), zscore_window).reindex(series.index)
    feature_series["roc_z_8w"] = _rolling_zscore_series(feature_series["roc_8w"].dropna(), zscore_window).reindex(series.index)
    features: dict[str, Any] = {name: float(values.dropna().iloc[-1]) if not values.dropna().empty else float("nan") for name, values in feature_series.items()}
    features["current"] = current
    features["_series"] = feature_series
    return features


def _stress_state_for_row(ticker: str, features: dict[str, Any], definitions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    definition = definitions.get(ticker, {"thresholds": {}, "weight": 1.0})
    thresholds = definition.get("thresholds", {})
    level = _determine_level(features, thresholds)
    reached = thresholds.get(level) if level != "normal" else None
    reason = _build_reason(features, level, reached)
    signal = f"{ticker_label_ja(ticker)}は {LEVEL_LABELS[level]}"
    return {
        "line_level": level,
        "signal_label": signal,
        "line_reason": reason,
        "warning_line": _threshold_value_for_display(ticker, thresholds, "warning"),
        "danger_line": _threshold_value_for_display(ticker, thresholds, "danger"),
        "extreme_line": _threshold_value_for_display(ticker, thresholds, "extreme"),
        "recent_warning_hits": _recent_hits_for_stage(features, thresholds.get("warning")),
        "recent_danger_hits": _recent_hits_for_stage(features, thresholds.get("danger")),
        "recent_extreme_hits": _recent_hits_for_stage(features, thresholds.get("extreme")),
        "weight": float(definition.get("weight", 1.0)),
        "pressure_score": _pressure_score(features, thresholds),
    }


def _determine_level(features: dict[str, Any], thresholds: dict[str, dict[str, Any]]) -> str:
    for stage in ("extreme", "danger", "warning"):
        rule = thresholds.get(stage)
        if rule and _rule_triggered(features, rule):
            return stage
    return "normal"


def _rule_triggered(features: dict[str, Any], rule: dict[str, Any]) -> bool:
    feature_name = str(rule.get("feature", ""))
    value = features.get(feature_name)
    threshold = rule.get("threshold")
    direction = str(rule.get("direction", "higher"))
    if value is None or threshold is None or pd.isna(value):
        return False
    if direction == "lower":
        return float(value) <= float(threshold)
    return float(value) >= float(threshold)


def _build_reason(features: dict[str, Any], level: str, rule: dict[str, Any] | None) -> str:
    if level == "normal" or not rule:
        return "reality-checked で採用された基準には未到達です。"
    feature_name = str(rule.get("feature", "-"))
    value = features.get(feature_name)
    threshold = rule.get("threshold")
    direction = "以上" if str(rule.get("direction", "higher")) == "higher" else "以下"
    return f"{feature_name} が {float(value):.4f} で、採用基準 {float(threshold):.4f} {direction} を満たしています。"


def _threshold_value_for_display(ticker: str, thresholds: dict[str, dict[str, Any]], stage: str) -> str:
    rule = thresholds.get(stage)
    if not rule:
        decision = _registry_stage_decision(ticker, stage)
        if decision == "review":
            return "見直し中"
        if decision == "reject":
            return "未採用"
        return "基準なし"
    return f"{rule.get('feature')}:{rule.get('threshold')}"


@lru_cache(maxsize=1)
def _load_model_registry() -> dict[str, Any]:
    if not MODEL_REGISTRY_PATH.exists():
        return {}
    try:
        return json.loads(MODEL_REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _registry_stage_decision(ticker: str, stage: str) -> str | None:
    registry = _load_model_registry()
    target_name = f"{stage}_target"
    review_targets = ((registry.get("review_queue") or {}).get(ticker) or {}).get("targets") or {}
    if target_name in review_targets:
        return "review"
    rejected_targets = ((registry.get("rejected_targets") or {}).get(ticker) or {}).get("targets") or {}
    if target_name in rejected_targets:
        return "reject"
    live_targets = ((registry.get("live_models") or {}).get(ticker) or {}).get("targets") or {}
    if target_name in live_targets:
        return "adopt"
    return None


def _recent_hits_for_stage(features: dict[str, Any], rule: dict[str, Any] | None) -> int:
    if not rule:
        return 0
    series = features.get("_series", {}).get(str(rule.get("feature", "")))
    if series is None or series.empty:
        return 0
    tail = series.dropna().tail(5)
    if tail.empty:
        return 0
    threshold = float(rule.get("threshold"))
    direction = str(rule.get("direction", "higher"))
    if direction == "lower":
        return int((tail <= threshold).sum())
    return int((tail >= threshold).sum())


def _pressure_score(features: dict[str, Any], thresholds: dict[str, dict[str, Any]]) -> float:
    reached_rank = 0
    highest_ratio = 0.0
    for stage, rank in (("warning", 1), ("danger", 2), ("extreme", 3)):
        rule = thresholds.get(stage)
        if not rule:
            continue
        ratio = _rule_distance_ratio(features, rule)
        highest_ratio = max(highest_ratio, ratio)
        if _rule_triggered(features, rule):
            reached_rank = max(reached_rank, rank)
    if reached_rank > 0:
        return min(0.33 * reached_rank + 0.01 * highest_ratio, 1.0)
    return min(highest_ratio * 0.33, 0.32)


def _rule_distance_ratio(features: dict[str, Any], rule: dict[str, Any]) -> float:
    feature_name = str(rule.get("feature", ""))
    value = features.get(feature_name)
    threshold = rule.get("threshold")
    if value is None or threshold in {None, 0} or pd.isna(value):
        return 0.0
    threshold = float(threshold)
    if str(rule.get("direction", "higher")) == "lower":
        adverse = abs(min(float(value), 0.0))
        base = abs(threshold) if threshold != 0 else 1.0
        return min(adverse / base, 1.0)
    return min(max(float(value), 0.0) / abs(threshold), 1.0)


def _rolling_zscore_series(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).apply(_zscore_last_window, raw=False)


def _rolling_percentile_series(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).apply(_percentile_last_window, raw=False)


def _drawdown_series(series: pd.Series, lookback: int) -> pd.Series:
    rolling_peak = series.rolling(lookback, min_periods=lookback).max()
    return series / rolling_peak - 1.0


def _zscore_last_window(window_series: pd.Series) -> float:
    clean = window_series.dropna()
    if len(clean) < 2:
        return float("nan")
    std = float(clean.std(ddof=0))
    if std == 0:
        return float("nan")
    return (float(clean.iloc[-1]) - float(clean.mean())) / std


def _percentile_last_window(window_series: pd.Series) -> float:
    clean = window_series.dropna()
    if len(clean) < 2:
        return float("nan")
    return float(clean.rank(method="average", pct=True).iloc[-1])
