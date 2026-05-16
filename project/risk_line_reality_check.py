from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from project.risk_line_feature_library import build_risk_line_feature_frames
from project.risk_line_label_builder import RiskLabelConfig, build_risk_event_labels


TARGET_CONFIG = {
    "warning_target": {
        "precision_min": 0.3,
        "false_positive_rate_max": 0.32,
        "min_f1_ratio": 0.82,
        "lower_quantile_max": 0.4,
        "higher_quantile_min": 0.6,
        "severity_floor": 0.35,
        "review_sanity_min": 2.8,
    },
    "danger_target": {
        "precision_min": 0.26,
        "false_positive_rate_max": 0.24,
        "min_f1_ratio": 0.8,
        "lower_quantile_max": 0.24,
        "higher_quantile_min": 0.76,
        "severity_floor": 0.22,
        "review_sanity_min": 2.5,
    },
    "extreme_target": {
        "precision_min": 0.18,
        "false_positive_rate_max": 0.16,
        "min_f1_ratio": 0.75,
        "lower_quantile_max": 0.12,
        "higher_quantile_min": 0.88,
        "severity_floor": 0.1,
        "review_sanity_min": 2.1,
    },
}


@dataclass(frozen=True)
class AnchorMetric:
    feature_name: str
    mode: str


ANCHOR_MAP: dict[str, list[AnchorMetric]] = {
    "current": [AnchorMetric("current", "raw")],
    "level_zscore": [AnchorMetric("current", "derived_current")],
    "level_percentile": [AnchorMetric("current", "derived_current")],
    "roc_1w": [AnchorMetric("roc_1w", "raw")],
    "roc_2w": [AnchorMetric("roc_2w", "raw")],
    "roc_4w": [AnchorMetric("roc_4w", "raw")],
    "roc_8w": [AnchorMetric("roc_8w", "raw")],
    "roc_z_1w": [AnchorMetric("roc_1w", "derived_roc")],
    "roc_z_2w": [AnchorMetric("roc_2w", "derived_roc")],
    "roc_z_4w": [AnchorMetric("roc_4w", "derived_roc")],
    "roc_z_8w": [AnchorMetric("roc_8w", "derived_roc")],
    "drawdown_13w": [AnchorMetric("drawdown_13w", "raw")],
    "drawdown_zscore": [AnchorMetric("drawdown_13w", "derived_drawdown")],
    "level_and_roc_4w": [AnchorMetric("current", "derived_current"), AnchorMetric("roc_4w", "derived_roc")],
    "level_and_roc_8w": [AnchorMetric("current", "derived_current"), AnchorMetric("roc_8w", "derived_roc")],
    "drawdown_and_roc_4w": [AnchorMetric("drawdown_13w", "derived_drawdown"), AnchorMetric("roc_4w", "derived_roc")],
}


STAGE_ORDER = ("warning_target", "danger_target", "extreme_target")


def build_reality_checked_thresholds(
    prices: pd.DataFrame,
    backtest_report: dict[str, Any],
    label_config: RiskLabelConfig | None = None,
) -> dict[str, Any]:
    feature_frames = build_risk_line_feature_frames(prices)
    labels = build_risk_event_labels(prices, config=label_config)
    indicators: dict[str, Any] = {}
    decision_counts = {"adopt": 0, "fallback_review": 0, "fallback_guarded": 0}
    for ticker, payload in backtest_report.get("indicators", {}).items():
        frame = feature_frames.get(ticker)
        if frame is None:
            continue
        indicator_result = _rebuild_indicator_thresholds(frame, labels, payload)
        indicators[ticker] = indicator_result
        for target_payload in indicator_result["targets"].values():
            decision = str(target_payload.get("decision", "fallback_guarded"))
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
    return {
        "indicator_count": len(indicators),
        "targets": list(backtest_report.get("targets", [])),
        "decision_counts": decision_counts,
        "indicators": indicators,
    }


def _rebuild_indicator_thresholds(
    frame: pd.DataFrame,
    labels: pd.DataFrame,
    payload: dict[str, Any],
) -> dict[str, Any]:
    targets: dict[str, Any] = {}
    for target in STAGE_ORDER:
        summary = payload.get("targets", {}).get(target, {})
        targets[target] = _choose_reality_checked_candidate(frame, labels, payload, target, summary)
    ordering_checks = _stage_ordering_checks(frame, payload, targets)
    return {
        "family": payload.get("family", "-"),
        "adverse_direction": payload.get("adverse_direction", "-"),
        "targets": targets,
        "ordering_checks": ordering_checks,
    }


def _choose_reality_checked_candidate(
    frame: pd.DataFrame,
    labels: pd.DataFrame,
    payload: dict[str, Any],
    target: str,
    summary: dict[str, Any],
) -> dict[str, Any]:
    best = dict(summary.get("best") or {})
    top_candidates = [dict(candidate) for candidate in summary.get("top_candidates", [])]
    if best and not top_candidates:
        top_candidates = [best]
    if not top_candidates:
        return {
            "decision": "fallback_guarded",
            "selection_mode": "fallback_guarded",
            "coverage_forced": True,
            "reason": "no_candidate_available",
            "selected_model": None,
            "metrics": None,
            "actual_value_check": {"status": "reject", "sanity_score": 0.0, "reasons": ["no_candidate_available"], "anchors": []},
            "candidate_reviews": [],
            "raw_value_reference": [],
            "frequency_profile": {},
        }

    best_f1 = float(best.get("f1", 0.0) or 0.0)
    adverse_direction = str(payload.get("adverse_direction", "lower"))
    assessed = [
        _assess_candidate(frame, labels, target, candidate, adverse_direction, str(payload.get("family", "-")), best_f1)
        for candidate in top_candidates
    ]
    assessed.sort(key=_candidate_sort_key, reverse=True)

    passing = [row for row in assessed if row["status"] == "pass"]
    near = [row for row in assessed if row["status"] == "review"]
    if passing:
        selected = passing[0]
        decision = "adopt"
        selection_mode = "adopt"
        coverage_forced = False
        reason = "passes_backtest_and_actual_value_check"
    elif near:
        selected = near[0]
        decision = "fallback_review"
        selection_mode = "fallback_review"
        coverage_forced = True
        reason = "coverage_fallback_from_review"
    else:
        selected = assessed[0]
        decision = "fallback_guarded"
        selection_mode = "fallback_guarded"
        coverage_forced = True
        reason = "coverage_fallback_from_guarded_candidate"

    anchors = selected.get("anchors", [])
    return {
        "decision": decision,
        "selection_mode": selection_mode,
        "coverage_forced": coverage_forced,
        "reason": reason,
        "selected_model": {
            "feature": selected["candidate"].get("feature"),
            "threshold": selected["candidate"].get("threshold"),
            "quantile": selected["candidate"].get("quantile"),
        },
        "metrics": _selected_metrics(selected["candidate"]),
        "actual_value_check": {
            "status": selected["status"],
            "sanity_score": round(float(selected["sanity_score"]), 4),
            "interpretability": selected["interpretability"]["label"],
            "reasons": selected["reasons"],
            "anchors": anchors,
        },
        "raw_value_reference": anchors,
        "frequency_profile": selected["frequency_profile"],
        "candidate_reviews": [
            {
                "feature": row["candidate"].get("feature"),
                "threshold": row["candidate"].get("threshold"),
                "quantile": row["candidate"].get("quantile"),
                "status": row["status"],
                "sanity_score": round(float(row["sanity_score"]), 4),
                "predicted_count": row["frequency_profile"].get("predicted_count"),
                "coverage": row["frequency_profile"].get("coverage"),
                "reasons": row["reasons"],
            }
            for row in assessed
        ],
    }


def _candidate_sort_key(row: dict[str, Any]) -> tuple[float, float, float, int]:
    candidate = row["candidate"]
    return (
        float(row.get("sanity_score", 0.0) or 0.0),
        float(candidate.get("f1", 0.0) or 0.0),
        float(candidate.get("precision", 0.0) or 0.0),
        int(row.get("interpretability", {}).get("rank", 0)),
    )


def _assess_candidate(
    frame: pd.DataFrame,
    labels: pd.DataFrame,
    target: str,
    candidate: dict[str, Any],
    adverse_direction: str,
    family: str,
    best_f1: float,
) -> dict[str, Any]:
    feature_name = str(candidate.get("feature"))
    cfg = TARGET_CONFIG[target]
    reasons: list[str] = []
    sanity_score = 0.0

    f1 = float(candidate.get("f1", 0.0) or 0.0)
    precision = float(candidate.get("precision", 0.0) or 0.0)
    false_positive_rate = float(candidate.get("false_positive_rate", 1.0) or 1.0)
    quantile = float(candidate.get("quantile", 0.0) or 0.0)

    if best_f1 and f1 >= best_f1 * cfg["min_f1_ratio"]:
        sanity_score += 1.0
    else:
        reasons.append("full_sample_f1_is_too_far_below_best_candidate")

    if precision >= cfg["precision_min"]:
        sanity_score += 1.0
    else:
        reasons.append("precision_is_too_low_for_stage")

    if false_positive_rate <= cfg["false_positive_rate_max"]:
        sanity_score += 1.0
    else:
        reasons.append("false_positive_rate_is_too_high_for_stage")

    if _quantile_shape_ok(target, adverse_direction, quantile):
        sanity_score += 1.0
    else:
        reasons.append("candidate_quantile_does_not_match_stage_severity")

    interpretability = _interpretability(feature_name, family)
    sanity_score += interpretability["score"]
    if not interpretability["pass"]:
        reasons.append(interpretability["reason"])

    anchors = _actual_anchors(frame, labels, target, adverse_direction, candidate)
    if anchors:
        floor = float(cfg["severity_floor"])
        if all(anchor.get("severity_score", 0.0) >= floor for anchor in anchors):
            sanity_score += 1.5
        else:
            reasons.append("triggered_true_positives_do_not_look_severe_enough_in_actual_values")
    else:
        reasons.append("actual_value_anchor_is_not_available")

    frequency_profile = _frequency_profile(candidate)
    if target == "warning_target" and float(frequency_profile.get("coverage", 0.0) or 0.0) < 0.02:
        reasons.append("warning_stage_is_too_sparse")
    if target == "extreme_target" and float(frequency_profile.get("coverage", 0.0) or 0.0) > 0.25:
        reasons.append("extreme_stage_is_too_frequent")

    if not reasons:
        status = "pass"
    elif sanity_score >= float(cfg["review_sanity_min"]):
        status = "review"
    else:
        status = "reject"

    return {
        "candidate": candidate,
        "status": status,
        "sanity_score": sanity_score,
        "reasons": reasons,
        "anchors": anchors,
        "interpretability": interpretability,
        "frequency_profile": frequency_profile,
    }


def _quantile_shape_ok(target: str, adverse_direction: str, quantile: float) -> bool:
    cfg = TARGET_CONFIG[target]
    if adverse_direction == "lower":
        return quantile <= cfg["lower_quantile_max"]
    return quantile >= cfg["higher_quantile_min"]


def _interpretability(feature_name: str, family: str) -> dict[str, Any]:
    if feature_name == "current":
        return {"pass": False, "score": 0.0, "label": "absolute_level", "reason": "absolute_level_is_not_stable_enough_for_final_threshold", "rank": 0}
    if feature_name in {"roc_1w", "roc_2w", "roc_4w", "roc_8w", "drawdown_13w"}:
        return {"pass": True, "score": 1.0, "label": "raw", "reason": "", "rank": 4}
    if feature_name in {"level_percentile", "level_zscore", "roc_z_1w", "roc_z_2w", "roc_z_4w", "roc_z_8w", "drawdown_zscore"}:
        score = 0.8 if family != "price_shock" or feature_name != "level_percentile" else 0.55
        return {"pass": True, "score": score, "label": "anchored_transform", "reason": "", "rank": 3}
    if feature_name in {"level_and_roc_4w", "level_and_roc_8w", "drawdown_and_roc_4w"}:
        return {"pass": True, "score": 0.6, "label": "composite_transform", "reason": "", "rank": 2}
    if feature_name in {"adverse_persistence_4", "adverse_persistence_8"}:
        return {"pass": True, "score": 0.45, "label": "persistence", "reason": "", "rank": 1}
    return {"pass": False, "score": 0.0, "label": "opaque", "reason": "feature_is_too_opaque_for_final_threshold", "rank": 0}


def _actual_anchors(
    frame: pd.DataFrame,
    labels: pd.DataFrame,
    target: str,
    adverse_direction: str,
    candidate: dict[str, Any],
) -> list[dict[str, Any]]:
    feature_name = str(candidate.get("feature"))
    threshold = float(candidate.get("threshold", 0.0) or 0.0)
    feature = frame.get(feature_name)
    if feature is None:
        return []
    predicted = _predict(feature, threshold, adverse_direction)
    true_positive_mask = predicted & labels[target].astype(bool).reindex(frame.index).fillna(False)
    if not bool(true_positive_mask.any()):
        return []
    anchors = ANCHOR_MAP.get(feature_name, [])
    rows: list[dict[str, Any]] = []
    for anchor in anchors:
        anchor_series = frame.get(anchor.feature_name)
        if anchor_series is None:
            continue
        clean = anchor_series.dropna()
        tp_values = anchor_series[true_positive_mask].dropna()
        if clean.empty or tp_values.empty:
            continue
        median_tp_value = float(tp_values.median())
        full_quantile = _value_percentile(clean, median_tp_value)
        severity_score = 1.0 - full_quantile if adverse_direction == "lower" else full_quantile
        rows.append({
            "metric": anchor.feature_name,
            "mode": anchor.mode,
            "true_positive_median": round(median_tp_value, 6),
            "true_positive_p25": round(float(tp_values.quantile(0.25)), 6),
            "true_positive_p75": round(float(tp_values.quantile(0.75)), 6),
            "historical_percentile": round(full_quantile, 4),
            "severity_score": round(severity_score, 4),
        })
    return rows


def _predict(feature: pd.Series, threshold: float, adverse_direction: str) -> pd.Series:
    if adverse_direction == "higher":
        return feature >= threshold
    return feature <= threshold


def _value_percentile(series: pd.Series, value: float) -> float:
    if series.empty:
        return 0.5
    return float((series <= value).mean())


def _selected_metrics(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "full_f1": round(float(candidate.get("f1", 0.0) or 0.0), 4),
        "precision": candidate.get("precision"),
        "recall": candidate.get("recall"),
        "false_positive_rate": candidate.get("false_positive_rate"),
        "average_lead_weeks": candidate.get("average_lead_weeks"),
        "coverage": candidate.get("coverage"),
        "predicted_count": candidate.get("predicted_count"),
        "true_positive_count": candidate.get("true_positive_count"),
    }


def _frequency_profile(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "predicted_count": candidate.get("predicted_count"),
        "coverage": candidate.get("coverage"),
        "true_positive_count": candidate.get("true_positive_count"),
    }


def _stage_ordering_checks(frame: pd.DataFrame, payload: dict[str, Any], targets: dict[str, Any]) -> list[dict[str, Any]]:
    adverse_direction = str(payload.get("adverse_direction", "lower"))
    checks: list[dict[str, Any]] = []
    previous_count: int | None = None
    for target in STAGE_ORDER:
        summary = targets.get(target, {})
        model = summary.get("selected_model") or {}
        feature_name = str(model.get("feature") or "")
        threshold = model.get("threshold")
        status = "ok"
        detail = ""
        predicted_count = None
        if feature_name and threshold is not None and feature_name in frame.columns:
            predicted_count = int(_predict(frame[feature_name].dropna(), float(threshold), adverse_direction).sum())
            if previous_count is not None and predicted_count > previous_count:
                status = "warning"
                detail = "predicted_count_is_not_monotonic"
            previous_count = predicted_count
        checks.append({
            "target": target,
            "predicted_count": predicted_count,
            "status": status,
            "detail": detail,
        })
    return checks
