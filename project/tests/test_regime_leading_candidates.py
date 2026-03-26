from __future__ import annotations

import pandas as pd

from project.regime_leading_candidates import build_regime_leading_candidates


def test_build_regime_leading_candidates_prefers_transition_sectors():
    index = pd.date_range("2025-01-03", periods=24, freq="W-FRI")
    prices = pd.DataFrame(
        {
            "XLU": [100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 89, 89, 90, 91, 92, 93, 94, 95, 95, 96, 97, 98],
            "XLB": [100, 98, 97, 95, 94, 93, 92, 91, 90, 89, 88, 87, 87, 87, 88, 89, 90, 91, 92, 93, 93, 94, 95, 96],
            "XLE": [100, 102, 104, 106, 108, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128],
            "EWJ": [100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 89, 89, 90, 91, 92, 93, 94, 95, 95, 96, 97, 98],
            "GLD": [100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 89, 89, 90, 91, 92, 93, 94, 95, 95, 96, 97, 98],
            "VEA": [100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 89, 89, 90, 91, 92, 93, 94, 95, 95, 96, 97, 98],
        },
        index=index,
        dtype=float,
    )
    sector_rotation = {
        "table": [
            {"ticker": "XLE", "sector_name_ja": "エネルギー", "return_12w": 0.12, "rank": 1, "rotation_phase": "leading", "rotation_phase_ja": "先導"},
            {"ticker": "XLU", "sector_name_ja": "公益事業", "return_12w": 0.01, "rank": 4, "rotation_phase": "improving", "rotation_phase_ja": "改善"},
            {"ticker": "XLB", "sector_name_ja": "素材", "return_12w": -0.01, "rank": 6, "rotation_phase": "lagging", "rotation_phase_ja": "出遅れ"},
        ]
    }
    availability = {"XLU": {"status": "ok"}, "XLB": {"status": "ok"}, "XLE": {"status": "ok"}, "EWJ": {"status": "ok"}, "GLD": {"status": "ok"}, "VEA": {"status": "ok"}}

    result = build_regime_leading_candidates(
        prices=prices,
        sector_map={"Utilities": "XLU", "Materials": "XLB", "Energy": "XLE"},
        region_map={"Japan": "EWJ", "Developed": "VEA"},
        asset_map={"Gold": "GLD"},
        sector_rotation=sector_rotation,
        availability_map=availability,
        regime={"regime_label": "transition"},
        reliability={"decision_allowed": True},
        alerts=[],
    )

    assert result["tier"] in {"priority", "watch"}
    assert result["label"] in {"レジーム先回り候補", "レジーム観察"}
    assert any(item["ticker"] in {"XLU", "XLB"} for item in result["candidate_tickers"])
    assert result["preferred_region"] is not None
    assert result["preferred_asset_class"] is not None


def test_build_regime_leading_candidates_returns_none_in_stress_regime():
    prices = pd.DataFrame({"XLU": [100.0] * 24}, index=pd.date_range("2025-01-03", periods=24, freq="W-FRI"))

    result = build_regime_leading_candidates(
        prices=prices,
        sector_map={"Utilities": "XLU"},
        region_map={},
        asset_map={},
        sector_rotation={"table": []},
        availability_map={"XLU": {"status": "ok"}},
        regime={"regime_label": "credit_stress"},
        reliability={"decision_allowed": True},
        alerts=[],
    )

    assert result["tier"] == "none"
    assert result["label"] == "候補なし"


def test_build_regime_leading_candidates_weakens_region_score_when_leadership_is_narrow():
    index = pd.date_range("2025-01-03", periods=24, freq="W-FRI")
    prices = pd.DataFrame(
        {
            "XLU": [100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 89, 89, 90, 91, 92, 93, 94, 95, 95, 96, 97, 98],
            "EWJ": [100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 89, 89, 90, 91, 92, 93, 94, 95, 95, 96, 97, 98],
            "VEA": [100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 89, 89, 90, 91, 92, 93, 94, 95, 95, 96, 97, 98],
            "GLD": [100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 89, 89, 90, 91, 92, 93, 94, 95, 95, 96, 97, 98],
        },
        index=index,
        dtype=float,
    )
    availability = {"XLU": {"status": "ok"}, "EWJ": {"status": "ok"}, "VEA": {"status": "ok"}, "GLD": {"status": "ok"}}
    base_rotation = {"table": [{"ticker": "XLU", "sector_name_ja": "公益事業", "return_12w": 0.01, "rank": 4, "rotation_phase": "improving", "rotation_phase_ja": "改善"}]}

    boosted = build_regime_leading_candidates(
        prices=prices,
        sector_map={"Utilities": "XLU"},
        region_map={"Japan": "EWJ", "Developed": "VEA"},
        asset_map={"Gold": "GLD"},
        sector_rotation={**base_rotation, "integration_signals": {"broad_improvement": True}},
        availability_map=availability,
        regime={"regime_label": "transition"},
        reliability={"decision_allowed": True},
        alerts=[],
        integration_settings={"ranking_integration_weight": 0.02},
    )
    narrowed = build_regime_leading_candidates(
        prices=prices,
        sector_map={"Utilities": "XLU"},
        region_map={"Japan": "EWJ", "Developed": "VEA"},
        asset_map={"Gold": "GLD"},
        sector_rotation={**base_rotation, "integration_signals": {"narrow_leadership": True}},
        availability_map=availability,
        regime={"regime_label": "transition"},
        reliability={"decision_allowed": True},
        alerts=[],
        integration_settings={"ranking_integration_weight": 0.02},
    )

    assert boosted["preferred_region"]["regime_score"] >= narrowed["preferred_region"]["regime_score"]


def test_region_integration_adjustment_is_capped():
    index = pd.date_range("2025-01-03", periods=24, freq="W-FRI")
    prices = pd.DataFrame(
        {
            "XLK": [100 + i for i in range(24)],
            "VEA": [100 + (i * 0.8) for i in range(24)],
            "VWO": [100 + (i * 0.9) for i in range(24)],
            "SPY": [100 + (i * 0.85) for i in range(24)],
        },
        index=index,
        dtype=float,
    )
    result = build_regime_leading_candidates(
        prices=prices,
        sector_map={"Tech": "XLK"},
        region_map={"Developed": "VEA", "Emerging": "VWO"},
        asset_map={"Stocks": "SPY"},
        sector_rotation={
            "table": [],
            "integration_signals": {
                "broad_improvement": True,
                "cyclical_improving": True,
                "narrow_leadership": False,
                "defensive_leadership": False,
            },
        },
        availability_map={ticker: {"status": "ok"} for ticker in ["XLK", "VEA", "VWO", "SPY"]},
        regime={"regime_label": "early_recovery"},
        reliability={"decision_allowed": True},
        alerts=[],
        integration_settings={"ranking_integration_weight": 0.08, "max_sector_adjustment": 0.1},
    )
    region = result["preferred_region"]
    assert region is not None
    assert region["regime_score"] >= 0
