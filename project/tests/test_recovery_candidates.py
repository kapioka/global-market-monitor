from __future__ import annotations

import pandas as pd

from project.recovery_candidates import build_recovery_candidates


def test_build_recovery_candidates_returns_build_tier():
    index = pd.date_range("2025-01-03", periods=40, freq="W-FRI")
    prices = pd.DataFrame(
        {
            "GLD": [100, 98, 95, 92, 90, 88, 86, 84, 82, 80, 79, 78, 77, 76, 75, 74, 73, 72, 71, 70, 70, 70, 70, 70, 70, 70, 71, 72, 73, 74, 75, 75, 74, 73, 72, 72, 73, 74, 75, 76],
            "XLV": [100, 99, 98, 96, 94, 92, 90, 88, 86, 84, 83, 82, 81, 80, 79, 78, 77, 76, 75, 74, 74, 74, 74, 74, 74, 74, 75, 76, 77, 78, 79, 79, 78, 77, 76, 76, 77, 78, 79, 80],
        },
        index=index,
        dtype=float,
    )
    availability = {
        "GLD": {"status": "ok"},
        "XLV": {"status": "ok"},
    }

    result = build_recovery_candidates(
        prices=prices,
        asset_map={"Gold": "GLD"},
        sector_map={"Health": "XLV"},
        availability_map=availability,
        regime={"regime_label": "transition"},
        cycle={"phase_label": "recovery"},
        reliability={"decision_allowed": True},
        alerts=[],
    )

    assert result["tier"] == "build"
    assert result["label"] == "仕込み候補"
    assert len(result["candidate_tickers"]) >= 1


def test_build_recovery_candidates_returns_none_in_stress_regime():
    prices = pd.DataFrame({"GLD": [100.0] * 40}, index=pd.date_range("2025-01-03", periods=40, freq="W-FRI"))
    result = build_recovery_candidates(
        prices=prices,
        asset_map={"Gold": "GLD"},
        sector_map={},
        availability_map={"GLD": {"status": "ok"}},
        regime={"regime_label": "credit_stress"},
        cycle={"phase_label": "recovery"},
        reliability={"decision_allowed": True},
        alerts=[],
    )

    assert result["tier"] == "none"
    assert result["label"] == "候補なし"
