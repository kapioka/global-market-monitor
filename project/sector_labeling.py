from __future__ import annotations

from typing import Any, Mapping

from project.sector_vector_analysis import calculate_vector_length, classify_vector_direction


DEFAULT_CANDIDATE_CONFIG: dict[str, float] = {
    "center_radius_threshold": 0.35,
    "normalized_length_min": 0.85,
    "promising_length_min": 1.15,
    "promising_length_max": 2.75,
    "angle_consistency_threshold": 35.0,
    "single_week_spike_ratio": 1.8,
    "warning_normalized_length_min": 0.95,
}


def classify_sector_candidate(
    current_quadrant: str,
    vec1: tuple[float, float] | Mapping[str, float],
    vec2: tuple[float, float] | Mapping[str, float],
    normalized_length: float,
    consistency: float | Mapping[str, Any],
    radius: float,
    config: Mapping[str, float] | None = None,
) -> str:
    """Assign a conservative candidate label from vector behavior and location."""

    merged = _merge_config(config)
    if radius < merged["center_radius_threshold"]:
        return "様子見"

    prev_dx, prev_dy = _vector_xy(vec1)
    curr_dx, curr_dy = _vector_xy(vec2)
    prev_length = calculate_vector_length(prev_dx, prev_dy)
    curr_length = calculate_vector_length(curr_dx, curr_dy)
    current_direction = classify_vector_direction(curr_dx, curr_dy)
    consistency_score = _consistency_score(consistency)
    min_consistency = max(0.0, 1.0 - (merged["angle_consistency_threshold"] / 180.0))

    single_week_spike = (
        prev_length > 0
        and curr_length >= prev_length * merged["single_week_spike_ratio"]
        and consistency_score < min_consistency
    )
    if single_week_spike:
        return "監視"

    if current_quadrant == "weakening" and current_direction in {"weakening", "defensive"}:
        if normalized_length >= merged["warning_normalized_length_min"]:
            return "失速警戒"
        return "様子見"

    if current_quadrant in {"leading", "improving"}:
        if (
            current_direction in {"improving", "cyclical"}
            and merged["promising_length_min"] <= normalized_length <= merged["promising_length_max"]
            and consistency_score >= min_consistency
        ):
            return "有望"
        if normalized_length >= merged["normalized_length_min"]:
            return "監視"
        return "様子見"

    if current_quadrant == "lagging" and current_direction in {"improving", "cyclical"}:
        if consistency_score >= min_consistency and normalized_length >= merged["normalized_length_min"]:
            return "監視"

    return "様子見"


def _vector_xy(vec: tuple[float, float] | Mapping[str, float]) -> tuple[float, float]:
    if isinstance(vec, Mapping):
        return float(vec.get("dx", 0.0) or 0.0), float(vec.get("dy", 0.0) or 0.0)
    return float(vec[0]), float(vec[1])


def _consistency_score(consistency: float | Mapping[str, Any]) -> float:
    if isinstance(consistency, Mapping):
        return float(consistency.get("consistency_score", 0.0) or 0.0)
    return float(consistency)


def _merge_config(config: Mapping[str, float] | None) -> dict[str, float]:
    merged = dict(DEFAULT_CANDIDATE_CONFIG)
    if config:
        merged.update({key: float(value) for key, value in config.items()})
    return merged
