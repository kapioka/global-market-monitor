from __future__ import annotations

import pandas as pd

from project.risk_line_label_builder import RiskLabelConfig, build_risk_event_labels


def test_build_risk_event_labels_marks_warning_and_composite_extreme_windows():
    index = pd.date_range("2024-01-05", periods=8, freq="W-FRI")
    prices = pd.DataFrame(
        {
            "SPY": [100.0, 99.0, 95.0, 90.0, 89.0, 89.5, 90.0, 91.0],
            "HYG": [100.0, 99.8, 99.1, 98.7, 98.5, 98.5, 98.6, 98.7],
            "LQD": [100.0, 100.2, 100.3, 100.5, 100.6, 100.7, 100.8, 100.9],
            "^VIX": [18.0, 22.0, 29.0, 39.0, 42.0, 35.0, 28.0, 24.0],
        },
        index=index,
        dtype=float,
    )

    labels = build_risk_event_labels(prices, RiskLabelConfig())

    assert bool(labels.iloc[0]["warning_target"])
    assert bool(labels.iloc[1]["danger_target"])
    assert bool(labels.iloc[1]["extreme_target"])
    assert labels.iloc[1]["extreme_lead_weeks"] == 2.0
    assert int(labels.iloc[1]["extreme_trigger_count"]) >= 2
