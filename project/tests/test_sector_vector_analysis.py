from __future__ import annotations

import pandas as pd

from project.sector_labeling import classify_sector_candidate
from project.sector_structure_summary import summarize_sector_structure
from project.sector_vector_analysis import (
    calculate_direction_consistency,
    calculate_sector_vectors,
    calculate_vector_length,
    classify_vector_direction,
    normalize_vector_length,
)


def test_classify_vector_direction_uses_quadrant_buckets():
    assert classify_vector_direction(1.0, 1.0) == "improving"
    assert classify_vector_direction(-1.0, 1.0) == "defensive"
    assert classify_vector_direction(-1.0, -1.0) == "weakening"
    assert classify_vector_direction(1.0, -1.0) == "cyclical"
    assert classify_vector_direction(0.0, 0.0) == "flat"


def test_calculate_vector_length_returns_euclidean_distance():
    assert calculate_vector_length(3.0, 4.0) == 5.0


def test_normalize_vector_length_uses_positive_history_average():
    normalized = normalize_vector_length(2.0, [1.0, 1.0, 2.0])
    assert normalized == 1.5


def test_calculate_direction_consistency_reports_angle_gap():
    consistency = calculate_direction_consistency((1.0, 0.0), (0.0, 1.0))
    assert consistency["angle_diff_deg"] == 90.0
    assert consistency["consistency_score"] == 0.5
    assert consistency["is_consistent"] is False


def test_classify_sector_candidate_marks_promising_when_move_is_consistent():
    consistency = calculate_direction_consistency((0.7, 0.6), (0.8, 0.7))
    label = classify_sector_candidate(
        current_quadrant="improving",
        vec1=(0.7, 0.6),
        vec2=(0.8, 0.7),
        normalized_length=1.4,
        consistency=consistency,
        radius=1.1,
    )
    assert label == "有望"


def test_classify_sector_candidate_filters_center_noise():
    consistency = calculate_direction_consistency((0.2, 0.2), (0.2, 0.2))
    label = classify_sector_candidate(
        current_quadrant="center",
        vec1=(0.2, 0.2),
        vec2=(0.2, 0.2),
        normalized_length=1.3,
        consistency=consistency,
        radius=0.1,
    )
    assert label == "様子見"


def test_single_week_spike_does_not_become_promising_immediately():
    consistency = calculate_direction_consistency((-0.2, 0.2), (2.0, 2.0))
    label = classify_sector_candidate(
        current_quadrant="leading",
        vec1=(-0.2, 0.2),
        vec2=(2.0, 2.0),
        normalized_length=2.2,
        consistency=consistency,
        radius=1.6,
    )
    assert label != "有望"
    assert label == "監視"


def test_summarize_sector_structure_generates_market_internal_label():
    summary = summarize_sector_structure(
        {
            "XLK": {"ticker": "XLK", "candidate_label": "有望"},
            "XLF": {"ticker": "XLF", "candidate_label": "有望"},
            "XLI": {"ticker": "XLI", "candidate_label": "監視"},
            "XLP": {"ticker": "XLP", "candidate_label": "様子見"},
        }
    )
    assert summary["structure_label"] == "Cyclical Recovery"


def test_calculate_sector_vectors_builds_expected_metadata():
    history_df = pd.DataFrame(
        [
            {
                "sector": "XLK",
                "x_2w_ago": -0.5,
                "y_2w_ago": 0.2,
                "x_1w_ago": 0.0,
                "y_1w_ago": 0.6,
                "x_current": 0.7,
                "y_current": 1.1,
                "avg_length_12w": 0.5,
            }
        ]
    )

    result = calculate_sector_vectors(history_df)

    assert "XLK" in result
    assert result["XLK"]["current_quadrant"] == "leading"
    assert result["XLK"]["vectors"]["current"]["direction"] == "improving"
    assert result["XLK"]["normalized_length"] > 1.0
