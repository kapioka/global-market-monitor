from __future__ import annotations

import math
from typing import Any, Mapping

import pandas as pd


DEFAULT_VECTOR_CONFIG: dict[str, float] = {
    "flat_threshold": 1e-9,
    "acceleration_positive_threshold": 0.08,
    "acceleration_negative_threshold": -0.08,
}


def calculate_sector_vectors(
    history_df: pd.DataFrame,
    config: Mapping[str, float] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build per-sector vector analytics from three weekly coordinate points.

    Expected columns are:
    - ``sector``
    - ``x_2w_ago`` / ``y_2w_ago``
    - ``x_1w_ago`` / ``y_1w_ago``
    - ``x_current`` / ``y_current``

    Optional columns:
    - ``avg_length_12w`` or ``length_avg_12w`` for normalized-length scaling.
    """

    merged = _merge_config(config)
    required = {"sector", "x_2w_ago", "y_2w_ago", "x_1w_ago", "y_1w_ago", "x_current", "y_current"}
    missing = required.difference(history_df.columns)
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"history_df is missing required columns: {missing_list}")

    results: dict[str, dict[str, Any]] = {}
    for row in history_df.to_dict(orient="records"):
        sector = str(row["sector"])
        x2 = _as_float(row["x_2w_ago"])
        y2 = _as_float(row["y_2w_ago"])
        x1 = _as_float(row["x_1w_ago"])
        y1 = _as_float(row["y_1w_ago"])
        x0 = _as_float(row["x_current"])
        y0 = _as_float(row["y_current"])

        prev_dx = x1 - x2
        prev_dy = y1 - y2
        curr_dx = x0 - x1
        curr_dy = y0 - y1
        prev_length = calculate_vector_length(prev_dx, prev_dy)
        curr_length = calculate_vector_length(curr_dx, curr_dy)
        avg_length_12w = _resolve_avg_length_12w(row, fallback=prev_length)
        normalized_length = normalize_vector_length(curr_length, [avg_length_12w])
        acceleration = curr_length - prev_length
        normalized_acceleration = normalize_vector_length(acceleration, [avg_length_12w]) if acceleration > 0 else -normalize_vector_length(abs(acceleration), [avg_length_12w])
        consistency = calculate_direction_consistency((prev_dx, prev_dy), (curr_dx, curr_dy))
        previous_direction = classify_vector_direction(prev_dx, prev_dy, merged["flat_threshold"])
        current_direction = classify_vector_direction(curr_dx, curr_dy, merged["flat_threshold"])
        consistency["is_three_week_continuous"] = bool(
            previous_direction == current_direction and previous_direction != "flat"
        )
        consistency["direction_sequence"] = [previous_direction, current_direction]

        results[sector] = {
            "sector": sector,
            "points": {
                "two_weeks_ago": {"x": round(x2, 6), "y": round(y2, 6)},
                "one_week_ago": {"x": round(x1, 6), "y": round(y1, 6)},
                "current": {"x": round(x0, 6), "y": round(y0, 6)},
            },
            "vectors": {
                "previous": {
                    "dx": round(prev_dx, 6),
                    "dy": round(prev_dy, 6),
                    "length": round(prev_length, 6),
                    "direction": previous_direction,
                },
                "current": {
                    "dx": round(curr_dx, 6),
                    "dy": round(curr_dy, 6),
                    "length": round(curr_length, 6),
                    "direction": current_direction,
                },
            },
            "current_quadrant": _classify_quadrant(x0, y0, merged["flat_threshold"]),
            "radius": round(calculate_vector_length(x0, y0), 6),
            "normalized_length": round(normalized_length, 6),
            "avg_length_12w": round(avg_length_12w, 6),
            "acceleration": {
                "raw": round(acceleration, 6),
                "normalized": round(normalized_acceleration, 6),
                "state": _classify_acceleration(normalized_acceleration, merged),
            },
            "consistency": consistency,
        }
    return results


def classify_vector_direction(dx: float, dy: float, flat_threshold: float = 1e-9) -> str:
    """Classify a vector direction into a market-friendly directional bucket."""

    if abs(dx) <= flat_threshold and abs(dy) <= flat_threshold:
        return "flat"
    if dx >= 0 and dy >= 0:
        return "improving"
    if dx < 0 <= dy:
        return "defensive"
    if dx < 0 and dy < 0:
        return "weakening"
    return "cyclical"


def calculate_vector_length(dx: float, dy: float) -> float:
    """Return Euclidean vector length."""

    return math.hypot(float(dx), float(dy))


def normalize_vector_length(length: float, history_lengths: list[float]) -> float:
    """Normalize vector length by the average of positive historical lengths."""

    positives = [float(item) for item in history_lengths if float(item) > 0]
    if not positives:
        return 0.0
    baseline = sum(positives) / len(positives)
    if baseline <= 0:
        return 0.0
    return float(length) / baseline


def calculate_direction_consistency(
    vec1: tuple[float, float] | Mapping[str, float],
    vec2: tuple[float, float] | Mapping[str, float],
) -> dict[str, float | bool | list[str]]:
    """Compare two vectors and return angular consistency metadata."""

    dx1, dy1 = _vector_xy(vec1)
    dx2, dy2 = _vector_xy(vec2)
    length1 = calculate_vector_length(dx1, dy1)
    length2 = calculate_vector_length(dx2, dy2)
    if length1 <= 0 or length2 <= 0:
        return {
            "angle_diff_deg": 180.0,
            "consistency_score": 0.0,
            "is_consistent": False,
            "is_three_week_continuous": False,
            "direction_sequence": [classify_vector_direction(dx1, dy1), classify_vector_direction(dx2, dy2)],
        }

    angle1 = math.degrees(math.atan2(dy1, dx1))
    angle2 = math.degrees(math.atan2(dy2, dx2))
    diff = abs(angle2 - angle1)
    if diff > 180:
        diff = 360 - diff
    score = max(0.0, 1.0 - (diff / 180.0))
    return {
        "angle_diff_deg": round(diff, 6),
        "consistency_score": round(score, 6),
        "is_consistent": bool(diff <= 45.0),
        "is_three_week_continuous": False,
        "direction_sequence": [classify_vector_direction(dx1, dy1), classify_vector_direction(dx2, dy2)],
    }



def _classify_acceleration(normalized_acceleration: float, config: Mapping[str, float]) -> str:
    if normalized_acceleration >= float(config["acceleration_positive_threshold"]):
        return "accelerating"
    if normalized_acceleration <= float(config["acceleration_negative_threshold"]):
        return "decelerating"
    return "stable"


def _resolve_avg_length_12w(row: dict[str, Any], fallback: float) -> float:
    for key in ("avg_length_12w", "length_avg_12w"):
        value = row.get(key)
        if value is not None:
            resolved = _as_float(value)
            if resolved > 0:
                return resolved
    return float(fallback) if fallback > 0 else 1.0


def _classify_quadrant(x: float, y: float, flat_threshold: float) -> str:
    if abs(x) <= flat_threshold and abs(y) <= flat_threshold:
        return "center"
    if x >= 0 and y >= 0:
        return "leading"
    if x < 0 <= y:
        return "improving"
    if x < 0 and y < 0:
        return "lagging"
    return "weakening"


def _vector_xy(vec: tuple[float, float] | Mapping[str, float]) -> tuple[float, float]:
    if isinstance(vec, Mapping):
        return float(vec.get("dx", 0.0) or 0.0), float(vec.get("dy", 0.0) or 0.0)
    return float(vec[0]), float(vec[1])


def _as_float(value: Any) -> float:
    return float(value)


def _merge_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = dict(DEFAULT_VECTOR_CONFIG)
    if not config:
        return merged
    for key, value in config.items():
        if isinstance(value, Mapping) or isinstance(value, list):
            merged[key] = value
        else:
            merged[key] = float(value)
    return merged
