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
