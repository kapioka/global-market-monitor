from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from project.risk_feature_contract import build_point_in_time_feature_contract
from project.risk_line_threshold_store import DEFAULT_ACTIVE_DEFINITIONS, load_threshold_definitions
from project.threshold_metadata import rule_metadata, threshold_family
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
    features = _build_feature_values(clean, ticker, windows, zscore_window)
    feature_contract = build_point_in_time_feature_contract(
        clean,
        symbol=ticker,
        evaluation_date=clean.index[-1] if not clean.empty else pd.Timestamp.today().normalize(),
        source_kind="market_snapshot",
        price_type=_price_type_for_ticker(ticker),
        minimum_history=max(int(windows.get("long", 12)), int(zscore_window)),
    )
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
        "threshold_evidence": stress_state["threshold_evidence"],
        "diagnostic_rule_hits": stress_state["diagnostic_rule_hits"],
        "accepted_rule": stress_state["accepted_rule"],
        "warning_line": stress_state["warning_line"],
        "danger_line": stress_state["danger_line"],
        "extreme_line": stress_state["extreme_line"],
        "recent_warning_hits": stress_state["recent_warning_hits"],
        "recent_danger_hits": stress_state["recent_danger_hits"],
        "recent_extreme_hits": stress_state["recent_extreme_hits"],
        "weight": stress_state["weight"],
        "pressure_score": round(stress_state["pressure_score"], 4),
        "health_score": round(1.0 - stress_state["pressure_score"], 4),
        "observation_metadata": feature_contract["metadata"],
        "comparison_observation_dates": feature_contract["metadata"]["comparison_observation_dates"],
        "quality_flags": feature_contract["metadata"]["quality_flags"],
        "stage_eligible": feature_contract["metadata"]["stage_eligible"],
        "corroborative_eligible": feature_contract["metadata"]["corroborative_eligible"],
        "limitations": feature_contract["metadata"]["limitations"],
    }


def _price_type_for_ticker(ticker: str) -> str:
    if ticker == "HYG/LQD":
        return "ratio"
    family = threshold_family(ticker)
    if family == "rates":
        return "yield"
    if family in {"commodity_oil", "commodity_gold"}:
        return "continuous_futures"
    if family == "fx":
        return "index"
    if family == "volatility":
        return "index"
    return "adjusted_close"


def _build_feature_values(series: pd.Series, ticker: str, windows: dict[str, int], zscore_window: int) -> dict[str, Any]:
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
    feature_series["drawdown_zscore"] = _rolling_zscore_series(feature_series["drawdown_13w"].dropna(), zscore_window).reindex(series.index)
    feature_series.update(_build_composite_feature_series(ticker, feature_series))
    features: dict[str, Any] = {name: float(values.dropna().iloc[-1]) if not values.dropna().empty else float("nan") for name, values in feature_series.items()}
    features["current"] = current
    features["_series"] = feature_series
    return features


def _build_composite_feature_series(ticker: str, feature_series: dict[str, pd.Series]) -> dict[str, pd.Series]:
    family = threshold_family(ticker)
    if family in {"volatility", "rates", "commodity_oil", "commodity_gold", "fx"}:
        return {
            "level_and_roc_4w": _combine_high_side(feature_series["level_percentile"], feature_series["roc_z_4w"]),
            "level_and_roc_8w": _combine_high_side(feature_series["level_percentile"], feature_series["roc_z_8w"]),
        }
    if ticker == "HYG/LQD":
        return {
            "level_and_roc_4w": _combine_low_side(feature_series["level_zscore"], feature_series["roc_z_4w"]),
            "level_and_roc_8w": _combine_low_side(feature_series["level_zscore"], feature_series["roc_z_8w"]),
        }
    return {
        "drawdown_and_roc_4w": _combine_low_side(feature_series["drawdown_zscore"], feature_series["roc_z_4w"]),
        "level_and_roc_8w": _combine_low_side(feature_series["level_zscore"], feature_series["roc_z_8w"]),
    }


def _stress_state_for_row(ticker: str, features: dict[str, Any], definitions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    definition = definitions.get(ticker, {"thresholds": {}, "weight": 1.0})
    thresholds = definition.get("thresholds", {})
    evidence = _threshold_evidence(ticker, features, thresholds)
    level = _determine_level(evidence)
    accepted = next((row for row in evidence if row["stage"] == level and row["triggered"] and row["allowed_for_stage"]), None)
    diagnostic_hits = [row for row in evidence if row["triggered"] and not row["allowed_for_stage"]]
    reached = thresholds.get(level) if level != "normal" else None
    reason = _build_reason(features, level, reached, accepted, diagnostic_hits)
    signal = f"{ticker_label_ja(ticker)}は {LEVEL_LABELS[level]}"
    return {
        "line_level": level,
        "signal_label": signal,
        "line_reason": reason,
        "threshold_evidence": evidence,
        "diagnostic_rule_hits": diagnostic_hits,
        "accepted_rule": accepted or {},
        "warning_line": _threshold_value_for_display(ticker, thresholds, "warning"),
        "danger_line": _threshold_value_for_display(ticker, thresholds, "danger"),
        "extreme_line": _threshold_value_for_display(ticker, thresholds, "extreme"),
        "recent_warning_hits": _recent_hits_for_stage(features, thresholds.get("warning")),
        "recent_danger_hits": _recent_hits_for_stage(features, thresholds.get("danger")),
        "recent_extreme_hits": _recent_hits_for_stage(features, thresholds.get("extreme")),
        "weight": float(definition.get("weight", 1.0)),
        "pressure_score": _pressure_score(features, thresholds, evidence),
    }


def _determine_level(evidence: list[dict[str, Any]]) -> str:
    for stage in ("extreme", "danger", "warning"):
        rule = next((row for row in evidence if row["stage"] == stage), None)
        if rule and rule["triggered"] and rule["allowed_for_stage"]:
            return stage
    return "normal"


def _threshold_evidence(ticker: str, features: dict[str, Any], thresholds: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage in ("warning", "danger", "extreme"):
        rule = thresholds.get(stage)
        if not rule:
            continue
        metadata = rule_metadata(ticker, stage, rule)
        feature_name = str(rule.get("feature", ""))
        value = features.get(feature_name)
        triggered = _rule_triggered(features, rule)
        allowed = _rule_allowed_for_stage(rule, metadata)
        rows.append(
            {
                "stage": stage,
                "feature": feature_name,
                "value": _safe_float(value),
                "threshold": _safe_float(rule.get("threshold")),
                "direction": str(rule.get("direction", "higher")),
                "triggered": triggered,
                "allowed_for_stage": allowed,
                "source": metadata.get("source"),
                "confidence": metadata.get("confidence"),
                "review_status": metadata.get("review_status"),
                "reason": metadata.get("reason"),
                "allow_final_action": metadata.get("allow_final_action"),
                "allow_extreme_stage": metadata.get("allow_extreme_stage"),
            }
        )
    return rows


def _rule_allowed_for_stage(rule: dict[str, Any], metadata: dict[str, Any]) -> bool:
    source = str(metadata.get("source") or "")
    review_status = str(metadata.get("review_status") or "")
    if source == "fallback_review" or review_status == "fallback_review":
        return False
    if rule.get("coverage_forced"):
        return False
    return True


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


def _build_reason(
    features: dict[str, Any],
    level: str,
    rule: dict[str, Any] | None,
    accepted: dict[str, Any] | None,
    diagnostic_hits: list[dict[str, Any]],
) -> str:
    diagnostic_note = _diagnostic_note(diagnostic_hits)
    if level == "normal" or not rule or not accepted:
        base = "本判定に使える採用済み基準には未到達です。"
        return f"{base} {diagnostic_note}".strip()
    feature_name = str(rule.get("feature", "-"))
    value = features.get(feature_name)
    threshold = rule.get("threshold")
    direction = "以上" if str(rule.get("direction", "higher")) == "higher" else "以下"
    base = f"{feature_name} が {float(value):.4f} で、採用可能な基準 {float(threshold):.4f} {direction} を満たしています。"
    return f"{base} {diagnostic_note}".strip()


def _diagnostic_note(diagnostic_hits: list[dict[str, Any]]) -> str:
    if not diagnostic_hits:
        return ""
    parts = []
    for row in diagnostic_hits[:2]:
        stage = LEVEL_LABELS.get(str(row.get("stage")), str(row.get("stage")))
        feature = row.get("feature")
        value = row.get("value")
        threshold = row.get("threshold")
        confidence = row.get("confidence")
        parts.append(f"{stage}/{feature}={_format_float(value)} 対 基準 {_format_float(threshold)} は {confidence} のため参考扱い")
    return "参考シグナル: " + "、".join(parts) + "。"


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


def _pressure_score(features: dict[str, Any], thresholds: dict[str, dict[str, Any]], evidence: list[dict[str, Any]]) -> float:
    reached_rank = 0
    highest_ratio = 0.0
    for stage, rank in (("warning", 1), ("danger", 2), ("extreme", 3)):
        rule = thresholds.get(stage)
        if not rule:
            continue
        evidence_row = next((row for row in evidence if row["stage"] == stage), {})
        if not evidence_row.get("allowed_for_stage"):
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


def _combine_high_side(level_percentile: pd.Series, roc_z: pd.Series) -> pd.Series:
    return pd.concat([level_percentile, _positive_unit_scale(roc_z)], axis=1).max(axis=1)


def _combine_low_side(level: pd.Series, roc_z: pd.Series) -> pd.Series:
    return pd.concat([_negative_unit_scale(level), _negative_unit_scale(roc_z)], axis=1).max(axis=1)


def _positive_unit_scale(series: pd.Series) -> pd.Series:
    return series.clip(lower=0.0).div(3.0).clip(lower=0.0, upper=1.0)


def _negative_unit_scale(series: pd.Series) -> pd.Series:
    return series.mul(-1.0).clip(lower=0.0).div(3.0).clip(lower=0.0, upper=1.0)


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


def _safe_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_float(value: Any) -> str:
    numeric = _safe_float(value)
    if numeric is None:
        return "-"
    return f"{numeric:.4f}"


def _percentile_last_window(window_series: pd.Series) -> float:
    clean = window_series.dropna()
    if len(clean) < 2:
        return float("nan")
    return float(clean.rank(method="average", pct=True).iloc[-1])
