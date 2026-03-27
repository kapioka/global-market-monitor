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
    consistency["is_three_week_continuous"] = True
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
    assert summary["watch_share"] == 0.75
    assert summary["promising_share"] == 0.5
    assert "裾野は十分に広がっています。" in summary["reason"]
    assert "有望セクター比率は高めです。" in summary["reason"]


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


def test_promising_requires_three_week_direction_continuity():
    consistency = calculate_direction_consistency((0.6, 0.6), (0.8, -0.3))
    label = classify_sector_candidate(
        current_quadrant="leading",
        vec1=(0.6, 0.6),
        vec2=(0.8, -0.3),
        normalized_length=1.4,
        consistency=consistency,
        radius=1.1,
    )
    assert label == "監視"


def test_calculate_sector_vectors_marks_three_week_continuity():
    history_df = pd.DataFrame([
        {
            "sector": "XLK",
            "x_2w_ago": 0.1,
            "y_2w_ago": 0.2,
            "x_1w_ago": 0.5,
            "y_1w_ago": 0.6,
            "x_current": 0.9,
            "y_current": 1.0,
            "avg_length_12w": 0.5,
        }
    ])
    result = calculate_sector_vectors(history_df)
    assert result["XLK"]["consistency"]["is_three_week_continuous"] is True
    assert result["XLK"]["consistency"]["direction_sequence"] == ["improving", "improving"]


def test_summarize_sector_structure_detects_energy_dominance_warning():
    summary = summarize_sector_structure(
        {
            "XLE": {"ticker": "XLE", "candidate_label": "有望", "rank": 1},
            "XLK": {"ticker": "XLK", "candidate_label": "様子見", "rank": 4},
            "XLF": {"ticker": "XLF", "candidate_label": "様子見", "rank": 5},
        }
    )
    assert summary["energy_dominance"] is True


def test_summarize_sector_structure_reports_dispersion_score():
    summary = summarize_sector_structure(
        {
            "XLE": {"ticker": "XLE", "candidate_label": "有望"},
            "XLK": {"ticker": "XLK", "candidate_label": "監視"},
            "XLF": {"ticker": "XLF", "candidate_label": "様子見"},
            "XLI": {"ticker": "XLI", "candidate_label": "様子見"},
        }
    )
    assert summary["dispersion_score"] == 0.5


def test_summarize_sector_structure_avoids_narrow_label_when_dispersion_is_broad():
    summary = summarize_sector_structure(
        {
            "XLE": {"ticker": "XLE", "candidate_label": "有望"},
            "XLK": {"ticker": "XLK", "candidate_label": "監視"},
            "XLF": {"ticker": "XLF", "candidate_label": "監視"},
            "XLI": {"ticker": "XLI", "candidate_label": "監視"},
        }
    )
    assert summary["structure_label"] != "Narrow Leadership"


def test_energy_dominance_requires_top_rank_energy():
    summary = summarize_sector_structure(
        {
            "XLE": {"ticker": "XLE", "candidate_label": "有望", "rank": 3},
            "XLK": {"ticker": "XLK", "candidate_label": "様子見", "rank": 1},
            "XLF": {"ticker": "XLF", "candidate_label": "様子見", "rank": 2},
        }
    )
    assert summary["energy_dominance"] is False


def test_summarize_sector_structure_detects_non_energy_single_sector_dominance():
    summary = summarize_sector_structure(
        {
            "XLK": {"ticker": "XLK", "candidate_label": "有望", "rank": 1},
            "XLF": {"ticker": "XLF", "candidate_label": "様子見", "rank": 4},
            "XLI": {"ticker": "XLI", "candidate_label": "様子見", "rank": 5},
        }
    )
    assert summary["single_sector_dominance"] is True
    assert summary["dominant_sector"] == "XLK"
    assert summary["dominance_strength"] == "strong"
    assert summary["dominance_components"] == {"concentration": "high", "breadth_deficit": "high", "top_gap": "high"}
    assert summary["energy_dominance"] is False




def test_dominance_strength_weakens_when_breadth_is_less_extreme():
    summary = summarize_sector_structure(
        {
            "XLK": {"ticker": "XLK", "candidate_label": "有望", "rank": 1},
            "XLF": {"ticker": "XLF", "candidate_label": "監視", "rank": 2},
            "XLI": {"ticker": "XLI", "candidate_label": "様子見", "rank": 6},
            "XLP": {"ticker": "XLP", "candidate_label": "様子見", "rank": 7},
            "XLV": {"ticker": "XLV", "candidate_label": "様子見", "rank": 8},
            "XLU": {"ticker": "XLU", "candidate_label": "様子見", "rank": 9},
        }
    )
    assert summary["single_sector_dominance"] is True
    assert summary["dominance_strength"] in {"weak", "medium"}
    assert summary["dominance_components"]["concentration"] in {"medium", "low"}
    assert summary["dominance_components"]["breadth_deficit"] in {"medium", "high"}


def test_dominance_strength_can_be_tuned_by_config():
    candidate_map = {
        "XLK": {"ticker": "XLK", "candidate_label": "有望", "rank": 2},
        "XLF": {"ticker": "XLF", "candidate_label": "様子見", "rank": 5},
        "XLI": {"ticker": "XLI", "candidate_label": "様子見", "rank": 6},
    }
    baseline = summarize_sector_structure(candidate_map)
    tuned = summarize_sector_structure(
        candidate_map,
        config={
            "energy_dominance_rank_max": 2,
            "dominance_strong_rank_max": 2,
            "dominance_medium_active_max": 1,
            "dominance_medium_dispersion_buffer_per_sector": 1.5,
        },
    )
    assert baseline["dominance_strength"] is None
    assert tuned["dominance_strength"] == "strong"

def test_calculate_sector_vectors_reports_acceleration():
    history_df = pd.DataFrame([
        {
            "sector": "XLK",
            "x_2w_ago": 0.0,
            "y_2w_ago": 0.0,
            "x_1w_ago": 0.2,
            "y_1w_ago": 0.2,
            "x_current": 0.8,
            "y_current": 0.8,
            "avg_length_12w": 0.4,
        }
    ])
    result = calculate_sector_vectors(history_df)
    assert result["XLK"]["acceleration"]["state"] == "accelerating"


def test_decelerating_move_does_not_remain_promising():
    consistency = calculate_direction_consistency((0.8, 0.8), (0.2, 0.2))
    consistency["is_three_week_continuous"] = True
    consistency["acceleration_state"] = "decelerating"
    label = classify_sector_candidate(
        current_quadrant="leading",
        vec1=(0.8, 0.8),
        vec2=(0.2, 0.2),
        normalized_length=1.4,
        consistency=consistency,
        radius=1.1,
    )
    assert label == "監視"


def test_summarize_sector_structure_adds_three_layer_structure():
    summary = summarize_sector_structure(
        {
            "XLK": {"ticker": "XLK", "candidate_label": "有望", "rank": 1, "acceleration_state": "accelerating"},
            "XLF": {"ticker": "XLF", "candidate_label": "監視", "rank": 2, "acceleration_state": "accelerating"},
            "XLI": {"ticker": "XLI", "candidate_label": "監視", "rank": 3, "acceleration_state": "stable"},
            "XLP": {"ticker": "XLP", "candidate_label": "様子見", "rank": 6, "acceleration_state": "stable"},
        }
    )
    assert summary["structure"]["breadth"] in {"mixed", "broad"}
    assert summary["structure"]["leadership"] == "cyclical"
    assert summary["structure"]["stability"] == "accelerating"
    assert summary["structure_detail"]["consistency"] == "aligned"
    assert summary["structure_detail"]["momentum_quality"] == "accelerating"


def test_relative_thresholds_allow_broad_improvement_with_small_sample():
    summary = summarize_sector_structure(
        {
            "XLK": {"ticker": "XLK", "candidate_label": "有望", "rank": 1},
            "XLF": {"ticker": "XLF", "candidate_label": "有望", "rank": 2},
            "XLP": {"ticker": "XLP", "candidate_label": "監視", "rank": 3},
            "XLV": {"ticker": "XLV", "candidate_label": "監視", "rank": 4},
        }
    )
    assert summary["structure_label"] == "Broad Improvement"
    assert "改善は比較的分散しています。" in summary["reason"]


def test_top_share_thresholds_can_block_broad_improvement():
    summary = summarize_sector_structure(
        {
            "XLK": {"ticker": "XLK", "candidate_label": "有望", "rank": 1},
            "XLF": {"ticker": "XLF", "candidate_label": "有望", "rank": 2},
            "XLP": {"ticker": "XLP", "candidate_label": "監視", "rank": 3},
            "XLV": {"ticker": "XLV", "candidate_label": "監視", "rank": 4},
        },
        config={"broad_watch_share_threshold": 1.1},
    )
    assert summary["structure_label"] != "Broad Improvement"


def test_relative_thresholds_keep_single_sector_dominance_available_with_small_sample():
    summary = summarize_sector_structure(
        {
            "XLK": {"ticker": "XLK", "candidate_label": "有望", "rank": 1},
            "XLF": {"ticker": "XLF", "candidate_label": "監視", "rank": 2},
            "XLI": {"ticker": "XLI", "candidate_label": "様子見", "rank": 4},
            "XLP": {"ticker": "XLP", "candidate_label": "様子見", "rank": 5},
        }
    )
    assert summary["single_sector_dominance"] is True
    assert summary["dominant_sector"] == "XLK"


def test_calculate_sector_vectors_accepts_nested_config_values():
    history_df = pd.DataFrame([
        {
            "sector": "XLK",
            "x_2w_ago": 0.1,
            "y_2w_ago": 0.2,
            "x_1w_ago": 0.3,
            "y_1w_ago": 0.5,
            "x_current": 0.8,
            "y_current": 0.9,
            "avg_length_12w": 0.4,
        }
    ])
    result = calculate_sector_vectors(
        history_df,
        config={
            "flat_threshold": 1e-6,
            "sector_groups": {"defensive": ["XLP"], "cyclical": ["XLK"]},
        },
    )
    assert result["XLK"]["vectors"]["current"]["direction"] == "improving"


def test_classify_sector_candidate_accepts_nested_config_values():
    consistency = calculate_direction_consistency((0.6, 0.6), (0.8, 0.7))
    consistency["is_three_week_continuous"] = True
    label = classify_sector_candidate(
        current_quadrant="leading",
        vec1=(0.6, 0.6),
        vec2=(0.8, 0.7),
        normalized_length=1.4,
        consistency=consistency,
        radius=1.1,
        config={
            "promising_length_min": 1.1,
            "sector_groups": {"defensive": ["XLP"], "cyclical": ["XLK"]},
        },
    )
    assert label == "有望"


def test_summarize_sector_structure_accepts_nested_config_values():
    summary = summarize_sector_structure(
        {
            "XLK": {"ticker": "XLK", "candidate_label": "有望", "rank": 1},
            "XLF": {"ticker": "XLF", "candidate_label": "監視", "rank": 2},
            "XLP": {"ticker": "XLP", "candidate_label": "様子見", "rank": 4},
        },
        config={
            "dispersion_low_threshold": 0.34,
            "sector_groups": {"defensive": ["XLP"], "cyclical": ["XLK", "XLF"]},
        },
    )
    assert summary["structure_label"] in {"Cyclical Recovery", "Noisy / Unclear", "Narrow Leadership"}
