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
