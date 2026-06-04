from __future__ import annotations

from project.buy_decision_card import build_buy_decision_card
from project.domestic_danger_context import build_domestic_danger_context


def _inputs() -> dict:
    return {
        "multi_asset_candidates": {
            "affects_final_action": False,
            "affects_buy_readiness_score": False,
            "candidates": [
                {
                    "asset_class": "bond_jpy",
                    "symbol": "2510.T",
                    "display_name": "円建て債券確認",
                    "status": "informational",
                    "caution": "債券は金利上昇時に価格が下がることがあります。",
                    "japan_resident_context_components": {"domestic_rate": -10, "jpy_relevance": 15},
                },
                {
                    "asset_class": "reit_jp",
                    "symbol": "1343.T",
                    "display_name": "国内REIT確認",
                    "status": "informational",
                    "japan_resident_context_components": {"domestic_rate": -10},
                },
                {
                    "asset_class": "jp_equity",
                    "symbol": "1306.T",
                    "display_name": "TOPIX連動ETF",
                    "status": "informational",
                    "japan_resident_context_components": {"trend": -3},
                },
            ],
        },
        "japan_risk": {"usd_jpy": {"ticker": "USDJPY=X", "ticker_name_ja": "米ドル円", "change_4w": 0.05}},
        "japan_resident_context": {
            "jgb_yields": {
                "jgb_2y": 1.402,
                "jgb_5y": 1.903,
                "jgb_10y": 2.52,
                "jgb_20y": 3.402,
                "jgb_30y": 3.721,
                "jgb_curve_10y_2y": 1.118,
                "jgb_curve_30y_10y": 1.201,
            },
            "macro_sources": {
                "japan_cpi": {"status": "manual_file_missing"},
                "boj_domestic_short_rate": {"status": "endpoint_not_resolved"},
            },
        },
        "acquisition_log": [
            {"requested_ticker": "1540.T", "used_ticker": "1540.T", "status": "ok", "used_ticker_name_ja": "純金上場信託"},
            {"requested_ticker": "1321.T", "used_ticker": "1321.T", "status": "ok", "used_ticker_name_ja": "日経225連動ETF"},
            {"requested_ticker": "EURJPY=X", "used_ticker": "EURJPY=X", "status": "ok", "used_ticker_name_ja": "ユーロ円"},
        ],
    }


def test_domestic_danger_context_uses_domestic_values_and_limitations() -> None:
    payload = build_domestic_danger_context(_inputs())

    groups = {row["group"] for row in payload["domestic_watch_items"]}
    assert payload["domestic_danger_level"] == "caution"
    assert payload["uses_domestic_values"] is True
    assert {"円建て債券", "国内REIT", "国内株式", "為替確認", "国内金利・国内インフレ", "円建て金"}.issubset(groups)
    assert any("JGB利回り" in row["reason"] for row in payload["domestic_watch_items"])
    assert any("CPI" in item and "manual_file_missing" in item for item in payload["domestic_data_limitations"])
    assert any("BOJ" in item and "endpoint_not_resolved" in item for item in payload["domestic_data_limitations"])
    assert payload["must_not_affect_final_action"] is True
    assert payload["must_not_affect_buy_readiness_score"] is True


def test_domestic_danger_context_keeps_foreign_and_domestic_assets_separate() -> None:
    payload = build_domestic_danger_context(_inputs())
    by_symbol = {row["symbol"]: row for row in payload["domestic_watch_items"]}

    assert by_symbol["2510.T"]["group"] == "円建て債券"
    assert "AGG" not in by_symbol
    assert by_symbol["1343.T"]["group"] == "国内REIT"
    assert "VNQ" not in by_symbol
    assert by_symbol["1540.T"]["group"] == "円建て金"
    assert "GLD" not in by_symbol


def test_missing_jgb_context_does_not_create_domestic_bond_or_reit_caution() -> None:
    inputs = _inputs()
    inputs["japan_resident_context"] = {"macro_sources": {}}
    for row in inputs["multi_asset_candidates"]["candidates"]:
        if row["asset_class"] in {"bond_jpy", "reit_jp"}:
            row["japan_resident_context_components"] = {"domestic_rate": 0}

    payload = build_domestic_danger_context(inputs)
    by_symbol = {row["symbol"]: row for row in payload["domestic_watch_items"]}

    assert by_symbol["2510.T"]["level"] != "caution"
    assert by_symbol["1343.T"]["level"] != "caution"
    assert any("MOF JGB利回りが未取得" in item for item in payload["domestic_data_limitations"])


def test_acquisition_log_only_does_not_create_watch_or_caution() -> None:
    payload = build_domestic_danger_context(
        {
            "multi_asset_candidates": {"candidates": []},
            "japan_risk": {},
            "japan_resident_context": {},
            "acquisition_log": [{"requested_ticker": "2510.T", "used_ticker": "2510.T", "status": "ok"}],
        }
    )
    by_symbol = {row["symbol"]: row for row in payload["domestic_watch_items"]}

    assert by_symbol["2510.T"]["level"] == "normal"
    assert payload["domestic_danger_level"] == "unavailable"


def test_domestic_danger_context_uses_real_price_metrics_for_equity_and_fx() -> None:
    payload = build_domestic_danger_context(
        {
            "multi_asset_candidates": {
                "candidates": [
                    {
                        "asset_class": "jp_equity",
                        "symbol": "1306.T",
                        "display_name": "TOPIX連動ETF",
                        "status": "informational",
                        "metrics": {"change_4w": -9.0, "change_12w": -12.0, "max_drawdown": -21.0, "trend_label": "falling"},
                        "japan_resident_context_components": {"domestic_rate": 0},
                    }
                ]
            },
            "japan_risk": {},
            "domestic_market_metrics": {
                "by_symbol": {"USDJPY=X": {"symbol": "USDJPY=X", "display_name": "米ドル円", "is_available": True, "change_4w": 5.0}}
            },
            "japan_resident_context": {},
            "acquisition_log": [],
        }
    )
    by_symbol = {row["symbol"]: row for row in payload["domestic_watch_items"]}

    assert by_symbol["1306.T"]["level"] == "caution"
    assert by_symbol["USDJPY=X"]["level"] == "caution"
    assert "4週=-9.0" in by_symbol["1306.T"]["metrics"]


def test_neutral_domestic_metrics_stay_normal_observed_context() -> None:
    payload = build_domestic_danger_context(
        {
            "multi_asset_candidates": {
                "candidates": [
                    {
                        "asset_class": "jp_equity",
                        "symbol": "1321.T",
                        "display_name": "日経225連動ETF",
                        "status": "informational",
                        "metrics": {"current_value": 120.0, "change_4w": 0.5, "change_12w": 1.2, "trend_label": "flat"},
                        "japan_resident_context_components": {"domestic_rate": 0},
                    }
                ]
            },
            "japan_risk": {},
            "japan_resident_context": {},
            "acquisition_log": [],
        }
    )

    by_symbol = {row["symbol"]: row for row in payload["domestic_watch_items"]}
    assert by_symbol["1321.T"]["level"] == "normal"


def test_reit_caution_requires_weakness_plus_rate_pressure() -> None:
    payload = build_domestic_danger_context(
        {
            "multi_asset_candidates": {
                "candidates": [
                    {
                        "asset_class": "reit_jp",
                        "symbol": "1343.T",
                        "display_name": "国内REIT確認",
                        "status": "informational",
                        "metrics": {"change_4w": -5.0, "change_12w": -9.0, "trend_label": "weakening"},
                        "japan_resident_context_components": {"domestic_rate": -8},
                    }
                ]
            },
            "japan_risk": {},
            "japan_resident_context": {},
            "acquisition_log": [],
        }
    )

    by_symbol = {row["symbol"]: row for row in payload["domestic_watch_items"]}
    assert by_symbol["1343.T"]["level"] == "caution"


def test_jpy_bond_weakness_plus_jgb_pressure_creates_caution() -> None:
    payload = build_domestic_danger_context(
        {
            "multi_asset_candidates": {
                "candidates": [
                    {
                        "asset_class": "bond_jpy",
                        "symbol": "2510.T",
                        "display_name": "円建て債券確認",
                        "status": "informational",
                        "metrics": {"change_4w": -4.5, "change_12w": -8.2, "trend_label": "weakening"},
                        "japan_resident_context_components": {"domestic_rate": -6},
                    }
                ]
            },
            "japan_risk": {},
            "japan_resident_context": {},
            "acquisition_log": [],
        }
    )

    by_symbol = {row["symbol"]: row for row in payload["domestic_watch_items"]}
    assert by_symbol["2510.T"]["level"] == "caution"


def test_eurjpy_metric_can_create_fx_caution_without_dxy_substitution() -> None:
    payload = build_domestic_danger_context(
        {
            "multi_asset_candidates": {"candidates": []},
            "japan_risk": {},
            "japan_resident_context": {},
            "domestic_market_metrics": {
                "by_symbol": {
                    "EURJPY=X": {
                        "symbol": "EURJPY=X",
                        "display_name": "ユーロ円",
                        "is_available": True,
                        "change_4w": -4.2,
                    }
                }
            },
            "acquisition_log": [],
        }
    )

    by_symbol = {row["symbol"]: row for row in payload["domestic_watch_items"]}
    assert by_symbol["EURJPY=X"]["level"] == "caution"
    assert "DX-Y.NYB" not in by_symbol


def test_domestic_danger_context_copy_avoids_advice_phrases() -> None:
    rendered = str(build_domestic_danger_context(_inputs()))

    for forbidden in ("買うべき", "今が買い", "安全", "利益が出る", "確実", "推奨銘柄"):
        assert forbidden not in rendered


def test_domestic_danger_context_does_not_change_buy_decision_card() -> None:
    report = {
        "spot_signal": {
            "action": "watch",
            "action_layers": {"market_raw_action": "watch", "risk_adjusted_action": "watch", "final_action": "watch"},
            "recovery_evidence": {"grade": "building"},
            "blocker_assessment": {"flags": ["japan_fx_risk_moderate"]},
        },
        "risk_lines": {"stage_key": "normal"},
        "data_reliability": {"level": "high", "decision_allowed": True},
        "score": {"total_score": 0.7},
    }
    baseline = build_buy_decision_card(report)
    report["domestic_danger_context"] = build_domestic_danger_context(_inputs())
    with_context = build_buy_decision_card(report)

    assert with_context["final_action"] == baseline["final_action"]
    assert with_context["buy_readiness_score"] == baseline["buy_readiness_score"]
