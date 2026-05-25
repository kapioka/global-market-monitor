from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from project.risk_line_feature_library import MODEL_SPECS, build_risk_line_feature_frames
from project.risk_line_label_builder import RiskLabelConfig, build_risk_event_labels


TARGETS = ("warning_target", "danger_target", "extreme_target")
LEAD_COLUMNS = {
    "warning_target": "warning_lead_weeks",
    "danger_target": "danger_lead_weeks",
    "extreme_target": "extreme_lead_weeks",
}


@dataclass(frozen=True)
class BacktestConfig:
    min_observations: int = 40
    quantiles: tuple[float, ...] = (0.1, 0.15, 0.2, 0.25, 0.3, 0.7, 0.75, 0.8, 0.85, 0.9)
    split_ratios: tuple[tuple[float, float], ...] = ((0.6, 0.2), (0.75, 0.15), (0.85, 0.1))
    walk_forward_train_size: int = 80
    walk_forward_test_size: int = 20
    walk_forward_step_size: int = 20


def build_risk_line_backtest_report(
    prices: pd.DataFrame,
    label_config: RiskLabelConfig | None = None,
    backtest_config: BacktestConfig | None = None,
) -> dict[str, Any]:
    cfg = backtest_config or BacktestConfig()
    labels = build_risk_event_labels(prices, config=label_config)
    feature_frames = build_risk_line_feature_frames(prices)

    indicators: dict[str, Any] = {}
    for ticker, frame in feature_frames.items():
        indicators[ticker] = _evaluate_indicator(ticker, frame, labels, cfg)

    return {
        "indicator_count": len(indicators),
        "targets": list(TARGETS),
        "indicators": indicators,
    }


def _evaluate_indicator(ticker: str, frame: pd.DataFrame, labels: pd.DataFrame, cfg: BacktestConfig) -> dict[str, Any]:
    spec = MODEL_SPECS[ticker]
    target_summaries: dict[str, Any] = {}
    excluded = {"current", "family", "adverse_direction"}
    feature_columns = [column for column in frame.columns if column not in excluded]
    for target in TARGETS:
        candidates: list[dict[str, Any]] = []
        for column in feature_columns:
            joined = _joined_frame(frame[column], labels, target)
            if len(joined) < cfg.min_observations:
                continue
            candidates.extend(_scan_feature_thresholds(joined, column, target, LEAD_COLUMNS[target], spec.adverse_direction, cfg.quantiles))
        candidates.sort(key=lambda row: (row["f1"], row["precision"], row["recall"]), reverse=True)
        best = candidates[0] if candidates else None
        target_summaries[target] = {
            "candidate_count": len(candidates),
            "best": best,
            "top_candidates": candidates[:10],
            "time_splits": _evaluate_time_splits(frame, labels, target, spec.adverse_direction, cfg, best),
            "walk_forward": _evaluate_walk_forward(frame, labels, target, spec.adverse_direction, cfg, best),
        }
    return {
        "family": spec.family,
        "adverse_direction": spec.adverse_direction,
        "rows": len(frame),
        "targets": target_summaries,
    }


def _joined_frame(feature: pd.Series, labels: pd.DataFrame, target: str) -> pd.DataFrame:
    return pd.concat([feature, labels[[target, LEAD_COLUMNS[target]]]], axis=1).dropna(subset=[feature.name, target])


def _aligned_split_inputs(frame: pd.DataFrame, labels: pd.DataFrame, target: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    common_index = frame.index.intersection(labels.index, sort=False)
    aligned_frame = frame.loc[common_index]
    aligned_labels = labels.loc[common_index]
    target_available = aligned_labels[target].notna()
    return aligned_frame.loc[target_available], aligned_labels.loc[target_available]


def _scan_feature_thresholds(
    joined: pd.DataFrame,
    feature_name: str,
    target_name: str,
    lead_name: str,
    adverse_direction: str,
    quantiles: tuple[float, ...],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    feature = joined[feature_name]
    target = joined[target_name].astype(bool)
    lead = joined[lead_name]
    valid_quantiles = [q for q in quantiles if 0.0 < q < 1.0]
    for quantile in valid_quantiles:
        threshold = float(feature.quantile(quantile))
        if adverse_direction == "higher":
            if quantile < 0.5:
                continue
            predicted = feature >= threshold
        else:
            if quantile > 0.5:
                continue
            predicted = feature <= threshold
        metrics = _classification_metrics(predicted, target, lead)
        if metrics is None:
            continue
        results.append({"feature": feature_name, "threshold": round(threshold, 6), "quantile": quantile, **metrics})
    return results


def _evaluate_time_splits(
    frame: pd.DataFrame,
    labels: pd.DataFrame,
    target: str,
    adverse_direction: str,
    cfg: BacktestConfig,
    best: dict[str, Any] | None,
) -> dict[str, Any]:
    if not best:
        return {"split_count": 0, "evaluations": []}
    evaluations: list[dict[str, Any]] = []
    for train_ratio, test_ratio in cfg.split_ratios:
        evaluation = _run_split(frame, labels, target, adverse_direction, cfg, train_ratio, test_ratio)
        if evaluation is not None:
            evaluations.append(evaluation)
    return {
        "split_count": len(evaluations),
        "evaluations": evaluations,
        "average_test_f1": _average_metric(evaluations, "test_f1"),
        "average_test_precision": _average_metric(evaluations, "test_precision"),
        "average_test_recall": _average_metric(evaluations, "test_recall"),
    }


def _run_split(
    frame: pd.DataFrame,
    labels: pd.DataFrame,
    target: str,
    adverse_direction: str,
    cfg: BacktestConfig,
    train_ratio: float,
    test_ratio: float,
) -> dict[str, Any] | None:
    frame, labels = _aligned_split_inputs(frame, labels, target)
    excluded = {"current", "family", "adverse_direction"}
    feature_columns = [column for column in frame.columns if column not in excluded]
    total = len(frame.index)
    train_end = int(total * train_ratio)
    test_end = int(total * (train_ratio + test_ratio))
    if test_end <= train_end or train_end < cfg.min_observations:
        return None
    split_index = frame.index
    train_mask = split_index < split_index[train_end]
    test_mask = (split_index >= split_index[train_end]) & (split_index < split_index[min(test_end, total - 1)])
    best_train: dict[str, Any] | None = None
    for column in feature_columns:
        joined = _joined_frame(frame.loc[train_mask, column], labels.loc[train_mask], target)
        if len(joined) < cfg.min_observations:
            continue
        candidates = _scan_feature_thresholds(joined, column, target, LEAD_COLUMNS[target], adverse_direction, cfg.quantiles)
        if not candidates:
            continue
        candidate = sorted(candidates, key=lambda row: (row["f1"], row["precision"], row["recall"]), reverse=True)[0]
        if best_train is None or (candidate["f1"], candidate["precision"], candidate["recall"]) > (best_train["f1"], best_train["precision"], best_train["recall"]):
            best_train = candidate
    if not best_train:
        return None
    test_joined = _joined_frame(frame.loc[test_mask, best_train["feature"]], labels.loc[test_mask], target)
    if len(test_joined) < max(10, cfg.min_observations // 2):
        return None
    predicted = _predict(test_joined[best_train["feature"]], adverse_direction, float(best_train["threshold"]))
    metrics = _classification_metrics(predicted, test_joined[target].astype(bool), test_joined[LEAD_COLUMNS[target]])
    if metrics is None:
        return None
    return {
        "train_ratio": train_ratio,
        "test_ratio": test_ratio,
        "feature": best_train["feature"],
        "threshold": best_train["threshold"],
        "train_f1": best_train["f1"],
        "test_f1": metrics["f1"],
        "test_precision": metrics["precision"],
        "test_recall": metrics["recall"],
        "test_false_positive_rate": metrics["false_positive_rate"],
    }


def _evaluate_walk_forward(
    frame: pd.DataFrame,
    labels: pd.DataFrame,
    target: str,
    adverse_direction: str,
    cfg: BacktestConfig,
    best: dict[str, Any] | None,
) -> dict[str, Any]:
    if not best:
        return {"window_count": 0, "evaluations": []}
    frame, labels = _aligned_split_inputs(frame, labels, target)
    excluded = {"current", "family", "adverse_direction"}
    feature_columns = [column for column in frame.columns if column not in excluded]
    index = frame.index
    evaluations: list[dict[str, Any]] = []
    start = cfg.walk_forward_train_size
    while start + cfg.walk_forward_test_size <= len(index):
        train_index = index[start - cfg.walk_forward_train_size : start]
        test_index = index[start : start + cfg.walk_forward_test_size]
        best_train: dict[str, Any] | None = None
        for column in feature_columns:
            joined = _joined_frame(frame.loc[train_index, column], labels.loc[train_index], target)
            if len(joined) < cfg.min_observations:
                continue
            candidates = _scan_feature_thresholds(joined, column, target, LEAD_COLUMNS[target], adverse_direction, cfg.quantiles)
            if not candidates:
                continue
            candidate = sorted(candidates, key=lambda row: (row["f1"], row["precision"], row["recall"]), reverse=True)[0]
            if best_train is None or (candidate["f1"], candidate["precision"], candidate["recall"]) > (best_train["f1"], best_train["precision"], best_train["recall"]):
                best_train = candidate
        if best_train:
            test_joined = _joined_frame(frame.loc[test_index, best_train["feature"]], labels.loc[test_index], target)
            if len(test_joined) >= max(8, cfg.min_observations // 3):
                predicted = _predict(test_joined[best_train["feature"]], adverse_direction, float(best_train["threshold"]))
                metrics = _classification_metrics(predicted, test_joined[target].astype(bool), test_joined[LEAD_COLUMNS[target]])
                if metrics:
                    evaluations.append({
                        "train_end": str(train_index[-1].date()),
                        "test_end": str(test_index[-1].date()),
                        "feature": best_train["feature"],
                        "threshold": best_train["threshold"],
                        "test_f1": metrics["f1"],
                        "test_precision": metrics["precision"],
                        "test_recall": metrics["recall"],
                    })
        start += cfg.walk_forward_step_size
    return {
        "window_count": len(evaluations),
        "evaluations": evaluations,
        "average_test_f1": _average_metric(evaluations, "test_f1"),
        "average_test_precision": _average_metric(evaluations, "test_precision"),
        "average_test_recall": _average_metric(evaluations, "test_recall"),
    }


def _predict(feature: pd.Series, adverse_direction: str, threshold: float) -> pd.Series:
    if adverse_direction == "higher":
        return feature >= threshold
    return feature <= threshold


def _average_metric(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _classification_metrics(predicted: pd.Series, target: pd.Series, lead: pd.Series) -> dict[str, Any] | None:
    tp = int((predicted & target).sum())
    fp = int((predicted & ~target).sum())
    fn = int((~predicted & target).sum())
    tn = int((~predicted & ~target).sum())
    if tp + fp + fn + tn == 0:
        return None
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 0.0 if precision + recall == 0 else 2.0 * precision * recall / (precision + recall)
    false_positive_rate = fp / (fp + tn) if fp + tn else 0.0
    predicted_count = int(predicted.sum())
    coverage = predicted_count / len(predicted) if len(predicted) else 0.0
    average_lead_weeks = float(lead[predicted & target].mean()) if tp else None
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(false_positive_rate, 4),
        "coverage": round(coverage, 4),
        "predicted_count": predicted_count,
        "true_positive_count": tp,
        "average_lead_weeks": round(average_lead_weeks, 4) if average_lead_weeks is not None else None,
    }
