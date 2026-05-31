from __future__ import annotations

from project.japan_resident_asset_context import (
    DATA_SOURCE_CONTRACT,
    JAPAN_RESIDENT_TAXONOMY,
    build_japan_resident_context_signal,
)


def test_taxonomy_covers_required_japan_resident_data_groups() -> None:
    required = {
        "bond_jpy_government",
        "bond_jpy_short",
        "bond_jpy_intermediate",
        "bond_jpy_long",
        "jgb_yield_curve",
        "fx_usdjpy",
        "equity_jp_topix",
        "equity_jp_nikkei",
        "equity_jp_broad",
        "jp_inflation",
        "jp_policy_rate",
        "reit_jp",
        "gold_usd",
        "gold_jpy_proxy",
        "foreign_bond",
    }

    assert required.issubset(JAPAN_RESIDENT_TAXONOMY)
    assert "config.tickers.japan.jp_reit_proxy" in DATA_SOURCE_CONTRACT["japanese_reit"]
    assert "config.tickers.japan.gold_jpy_proxy" in DATA_SOURCE_CONTRACT["gold_jpy_proxy"]
    assert "optional EURJPY=X acquisition log" in DATA_SOURCE_CONTRACT["fx_currency_context"]
    assert {
        "domestic_jpy_bonds",
        "jgb_yield_curve",
        "fx_currency_context",
        "japanese_equities",
        "japan_inflation_rates",
        "japanese_reit",
        "gold_jpy_proxy",
        "boj_domestic_rates",
    }.issubset(DATA_SOURCE_CONTRACT)


def test_missing_failed_partial_and_sample_data_are_gated_conservatively() -> None:
    missing = build_japan_resident_context_signal(
        {"asset_class": "bond_jpy_government", "source_data_available": False, "source_status": "missing"}
    )
    failed = build_japan_resident_context_signal(
        {"asset_class": "gold_jpy_proxy", "source_data_available": True, "source_status": "failed"}
    )
    partial = build_japan_resident_context_signal({"asset_class": "reit_jp", "source_data_available": True, "source_status": "partial"})
    sample = build_japan_resident_context_signal(
        {"asset_class": "equity_jp_topix", "source_data_available": True, "source_status": "sample_fallback"}
    )

    assert missing["status"] == "unavailable"
    assert failed["status"] == "unavailable"
    assert partial["status"] == "informational"
    assert sample["status"] == "informational"
    assert missing["context_score"] < 25
    assert partial["must_not_affect_final_action"] is True
    assert sample["must_not_affect_buy_readiness_score"] is True


def test_jpy_domestic_bond_uses_jgb_rate_context_without_becoming_decision_logic() -> None:
    falling_yields = build_japan_resident_context_signal(
        {
            "asset_class": "bond_jpy_intermediate",
            "source_data_available": True,
            "source_status": "ok",
            "metrics": {"momentum_12w": 0.03, "max_drawdown": -0.04},
        },
        {"jgb_yields": {"jgb_10y_change_4w": -0.08}},
    )
    rising_yields = build_japan_resident_context_signal(
        {
            "asset_class": "bond_jpy_long",
            "source_data_available": True,
            "source_status": "ok",
            "metrics": {"momentum_12w": 0.03, "max_drawdown": -0.04},
        },
        {"jgb_yields": {"jgb_10y_change_4w": 0.08}},
    )

    assert falling_yields["components"]["domestic_rate"] > 0
    assert rising_yields["components"]["domestic_rate"] < 0
    assert falling_yields["must_not_affect_final_action"] is True
    assert falling_yields["status"] in {"informational", "watch"}


def test_foreign_assets_require_fx_context_and_keep_caution() -> None:
    without_fx = build_japan_resident_context_signal(
        {
            "asset_class": "foreign_bond",
            "source_data_available": True,
            "source_status": "ok",
            "metrics": {"change_12w": 0.02},
        }
    )
    with_fx = build_japan_resident_context_signal(
        {
            "asset_class": "gold_usd",
            "source_data_available": True,
            "source_status": "ok",
            "metrics": {"change_12w": 0.03},
        },
        {"japan_risk": {"available": True, "usd_jpy": {"change_4w": -0.03}}},
    )

    assert without_fx["components"]["fx"] < 0
    assert without_fx["caution_required"] is True
    assert with_fx["components"]["fx"] < 0
    assert "売買指示ではありません" in with_fx["caution"]


def test_cash_gold_jp_equity_and_reit_are_separate_display_contexts() -> None:
    cash = build_japan_resident_context_signal(
        {"asset_class": "cash", "source_data_available": True, "source_status": "ok"},
        {"inflation": {"jp_cpi_trend": "high"}, "risk_lines": {"stage_key": "danger_line_reached"}},
    )
    gold = build_japan_resident_context_signal(
        {"asset_class": "gold_jpy_proxy", "source_data_available": True, "source_status": "ok"},
        {"inflation": {"jp_cpi_trend": "rising"}},
    )
    equity = build_japan_resident_context_signal(
        {"asset_class": "equity_jp_topix", "source_data_available": True, "source_status": "ok"},
        {"risk_lines": {"stage_key": "danger_line_reached"}},
    )
    reit = build_japan_resident_context_signal(
        {"asset_class": "reit_jp", "source_data_available": True, "source_status": "ok"},
        {"jgb_yields": {"jgb_10y_change_4w": 0.05}},
    )

    assert cash["status"] == "wait"
    assert gold["reason_category"] == "defensive_context"
    assert equity["reason_category"] == "jp_equity_context"
    assert reit["reason_category"] == "jp_reit_context"
    assert equity["components"]["market_risk"] < 0
    assert reit["components"]["domestic_rate"] < 0


def test_official_domestic_short_rate_context_is_display_only() -> None:
    cash = build_japan_resident_context_signal(
        {"asset_class": "cash", "source_data_available": True, "source_status": "ok"},
        {"domestic_rates": {"domestic_rate_context": "rising"}},
    )
    reit = build_japan_resident_context_signal(
        {"asset_class": "reit_jp", "source_data_available": True, "source_status": "ok"},
        {"domestic_rates": {"domestic_rate_context": "rising"}},
    )
    bond = build_japan_resident_context_signal(
        {"asset_class": "bond_jpy_intermediate", "source_data_available": True, "source_status": "ok"},
        {"domestic_rates": {"domestic_rate_context": "stable"}},
    )

    assert cash["components"]["domestic_rate"] > 0
    assert reit["components"]["domestic_rate"] < 0
    assert bond["components"]["domestic_rate"] > 0
    assert cash["must_not_affect_final_action"] is True
    assert reit["must_not_affect_buy_readiness_score"] is True


def test_official_jgb_yield_curve_levels_are_consumed_conservatively() -> None:
    high_yield = build_japan_resident_context_signal(
        {"asset_class": "bond_jpy_long", "source_data_available": True, "source_status": "ok"},
        {"jgb_yields": {"jgb_10y": 1.6, "jgb_curve_10y_2y": 0.7}},
    )
    low_yield = build_japan_resident_context_signal(
        {"asset_class": "bond_jpy_intermediate", "source_data_available": True, "source_status": "ok"},
        {"jgb_yields": {"jgb_10y": 0.4, "jgb_curve_10y_2y": 0.2}},
    )

    assert high_yield["components"]["domestic_rate"] < 0
    assert low_yield["components"]["domestic_rate"] > 0
    assert high_yield["must_not_affect_final_action"] is True
