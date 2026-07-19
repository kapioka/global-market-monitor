from __future__ import annotations

import pandas as pd

from project.stress_monitor import build_stress_monitor


def test_build_stress_monitor_marks_spy_warning_on_adopted_drawdown_rule():
    prices = pd.DataFrame(
        {
            "SPY": [100.0] * 13 + [97.0],
        }
    )

    rows = build_stress_monitor(
        prices,
        indicator_map={"SPY": "SPY"},
        windows={"short": 1, "medium": 4, "long": 12},
        zscore_window=52,
    )

    spy = next(row for row in rows if row["ticker"] == "SPY")
    assert spy["line_level"] == "warning"
    assert "drawdown_13w" in spy["warning_line"]


def test_build_stress_monitor_marks_hyg_danger_on_adopted_drawdown_rule():
    prices = pd.DataFrame(
        {
            "HYG": [100.0] * 13 + [97.5],
        }
    )

    rows = build_stress_monitor(
        prices,
        indicator_map={"HYG": "HYG"},
        windows={"short": 1, "medium": 4, "long": 12},
        zscore_window=52,
    )

    hyg = next(row for row in rows if row["ticker"] == "HYG")
    assert hyg["line_level"] == "danger"
    assert "drawdown_13w" in hyg["danger_line"]


def test_build_stress_monitor_marks_vix_extreme_on_reality_checked_percentile_rule():
    prices = pd.DataFrame(
        {
            "^VIX": list(range(1, 105)) + [105.0],
        }
    )

    rows = build_stress_monitor(
        prices,
        indicator_map={"VIX": "^VIX"},
        windows={"short": 1, "medium": 4, "long": 12},
        zscore_window=52,
    )

    vix = next(row for row in rows if row["ticker"] == "^VIX")
    assert vix["line_level"] == "extreme"
    assert "level_percentile" in vix["danger_line"]
    assert "level_percentile" in vix["extreme_line"]


def test_build_stress_monitor_uses_japanese_stage_placeholders_for_non_live_thresholds():
    prices = pd.DataFrame(
        {
            "CL=F": [100.0] * 60,
            "HYG": [100.0] * 60,
            "LQD": [100.0] * 60,
        }
    )

    rows = build_stress_monitor(
        prices,
        indicator_map={"WTI": "CL=F", "HYG": "HYG", "LQD": "LQD"},
        windows={"short": 1, "medium": 4, "long": 12},
        zscore_window=52,
    )

    wti = next(row for row in rows if row["ticker"] == "CL=F")
    ratio = next(row for row in rows if row["ticker"] == "HYG/LQD")
    assert "roc_8w" in wti["warning_line"]
    assert "level_and_roc_8w" in wti["danger_line"]
    assert "roc_2w" in wti["extreme_line"]
    assert "level_percentile" in ratio["warning_line"]
    assert "level_percentile" in ratio["danger_line"]
    assert "roc_z_8w" in ratio["extreme_line"]


def test_build_stress_monitor_keeps_fallback_review_extreme_as_diagnostic_evidence_only():
    prices = pd.DataFrame(
        {
            "DX-Y.NYB": [100.0] * 60 + [103.0],
        }
    )
    thresholds = {
        "DX-Y.NYB": {
            "weight": 0.85,
            "thresholds": {
                "extreme": {
                    "feature": "roc_z_1w",
                    "threshold": 1.0,
                    "direction": "higher",
                    "decision": "fallback_review",
                    "selection_mode": "fallback_review",
                    "coverage_forced": True,
                    "actual_value_check": {"status": "review", "reasons": ["precision_is_too_low_for_stage"]},
                }
            },
        }
    }

    rows = build_stress_monitor(
        prices,
        indicator_map={"DXY": "DX-Y.NYB"},
        windows={"short": 1, "medium": 4, "long": 12},
        zscore_window=20,
        threshold_definitions=thresholds,
    )

    dxy = next(row for row in rows if row["ticker"] == "DX-Y.NYB")
    assert dxy["line_level"] == "normal"
    assert dxy["pressure_score"] == 0
    assert dxy["diagnostic_rule_hits"][0]["stage"] == "extreme"
    assert dxy["diagnostic_rule_hits"][0]["allowed_for_stage"] is False
    assert "参考シグナル" in dxy["line_reason"]


def test_build_stress_monitor_exposes_rule_evidence_for_adopted_thresholds():
    prices = pd.DataFrame(
        {
            "SPY": [100.0] * 13 + [97.0],
        }
    )

    rows = build_stress_monitor(
        prices,
        indicator_map={"SPY": "SPY"},
        windows={"short": 1, "medium": 4, "long": 12},
        zscore_window=52,
    )

    spy = next(row for row in rows if row["ticker"] == "SPY")
    assert spy["line_level"] == "warning"
    assert spy["accepted_rule"]["stage"] == "warning"
    assert spy["threshold_evidence"]
    assert all("allowed_for_stage" in row for row in spy["threshold_evidence"])


def test_build_stress_monitor_exposes_composite_feature_values_for_review_thresholds():
    prices = pd.DataFrame(
        {
            "CL=F": [100.0] * 80 + [105.0, 110.0, 100.0, 95.0, 90.0, 87.0, 84.0, 80.0, 76.54],
        }
    )

    rows = build_stress_monitor(
        prices,
        indicator_map={"WTI": "CL=F"},
        windows={"short": 1, "medium": 4, "long": 12},
        zscore_window=20,
    )

    wti = next(row for row in rows if row["ticker"] == "CL=F")
    danger = next(row for row in wti["threshold_evidence"] if row["stage"] == "danger")

    assert danger["feature"] == "level_and_roc_8w"
    assert danger["value"] is not None
    assert danger["allowed_for_stage"] is False


def test_build_stress_monitor_exposes_observation_metadata_without_changing_stage():
    index = pd.bdate_range("2026-01-01", periods=70)
    prices = pd.DataFrame({"SPY": [100.0 + i for i in range(70)]}, index=index)

    rows = build_stress_monitor(
        prices,
        indicator_map={"SPY": "SPY"},
        windows={"short": 1, "medium": 4, "long": 12},
        zscore_window=20,
    )

    spy = next(row for row in rows if row["ticker"] == "SPY")
    assert spy["line_level"] == "normal"
    assert spy["observation_metadata"]["symbol"] == "SPY"
    assert spy["observation_metadata"]["price_type"] == "adjusted_close"
    assert spy["observation_metadata"]["latest_observation_date"] == index[-1].date().isoformat()
    assert spy["comparison_observation_dates"]["return_1w"] == index[-6].date().isoformat()
    assert spy["stage_eligible"] is True
    assert spy["quality_flags"] == ["valid"]
