from __future__ import annotations

from project.japan_resident_integrated_context import build_japan_resident_integrated_risk_context


def _inputs() -> dict:
    return {
        "risk_lines": {
            "stage_key": "credit_spillover_initial",
            "stage_label": "信用波及初期",
            "summary": "米国・グローバルの危険ラインは注意段階です。",
            "composite_risk_score": 48.2,
            "strict_missing_indicators": ["MOVE"],
        },
        "risk_line_confidence_audit": {
            "monitoring_scope_label": "米国・グローバル中心の危険監視",
            "dxy_role": {"label": "米ドル指数は米国・グローバルのドル高ストレス確認に使います。"},
            "jpy_fx_role": {"label": "USDJPY/EURJPY は日本円で見た外貨建て資産の円換算影響確認に使います。"},
        },
        "domestic_danger_context": {
            "domestic_danger_level": "watch",
            "domestic_danger_reasons": ["MOF JGB利回りは国内金利の補助危険確認に使われます。"],
            "domestic_watch_items": [
                {
                    "group": "円建て債券",
                    "asset_group": "bond_jpy",
                    "name": "円建て債券確認",
                    "level": "watch",
                    "reason": "円建て債券は国内金利と価格推移を分けて補助確認します。",
                    "source": "multi_asset_candidates",
                },
                {
                    "group": "為替確認",
                    "asset_group": "fx",
                    "name": "米ドル円",
                    "level": "caution",
                    "reason": "USDJPY=X の実変化で外貨建て資産の円換算影響を確認します。",
                    "source": "japan_risk",
                },
            ],
            "domestic_data_limitations": ["CPI は manual_file_missing のため補助危険値として扱いません。"],
        },
        "japan_risk": {"level": "moderate", "summary": "USDJPY=X は円建て換算影響の確認対象です。"},
        "japan_resident_context": {
            "jgb_yields": {"jgb_10y": 1.7},
            "macro_sources": {
                "japan_cpi": {"status": "manual_file_missing"},
                "boj_domestic_short_rate": {"status": "endpoint_not_resolved"},
            },
        },
    }


def test_integrated_context_combines_global_domestic_fx_rate_and_data_limitations() -> None:
    payload = build_japan_resident_integrated_risk_context(_inputs())

    assert payload["status"] == "display_only"
    assert payload["global_risk_level"] == "caution"
    assert payload["domestic_risk_level"] == "watch"
    assert payload["fx_risk_level"] == "caution"
    assert payload["rate_risk_level"] == "watch"
    assert payload["inflation_data_quality"] == "unavailable"
    assert payload["combined_context_level"] == "caution"
    assert payload["must_not_affect_final_action"] is True
    assert payload["must_not_affect_buy_readiness_score"] is True
    assert "risk_lines" in payload["source_sections"]
    assert "domestic_danger_context" in payload["source_sections"]


def test_integrated_context_keeps_dxy_and_jpy_fx_roles_separate() -> None:
    payload = build_japan_resident_integrated_risk_context(_inputs())
    rendered = str(payload)

    assert "米ドル指数" in rendered
    assert "USDJPY/EURJPY" in rendered
    assert "米国・グローバル" in rendered
    assert "日本円で見た外貨建て資産" in rendered


def test_integrated_context_treats_missing_macro_series_as_limitations() -> None:
    payload = build_japan_resident_integrated_risk_context(_inputs())

    assert any("CPI" in item and "manual_file_missing" in item for item in payload["data_limitations"])
    assert any("BOJ" in item and "endpoint_not_resolved" in item for item in payload["data_limitations"])
    assert any(row["group"] == "国内インフレ・国内金利データ" for row in payload["watch_items"])


def test_integrated_context_does_not_upgrade_neutral_usdjpy_summary_to_caution() -> None:
    inputs = _inputs()
    inputs["risk_lines"] = {"stage_key": "normal", "stage_label": "通常"}
    inputs["domestic_danger_context"] = {
        "domestic_danger_level": "normal",
        "domestic_watch_items": [],
        "domestic_data_limitations": [],
    }
    inputs["japan_risk"] = {"level": "moderate", "summary": "USDJPY は 中立 です。"}
    inputs["japan_resident_context"] = {"macro_sources": {}}

    payload = build_japan_resident_integrated_risk_context(inputs)

    assert payload["fx_risk_level"] == "normal"
    assert payload["combined_context_level"] == "normal"


def test_integrated_context_copy_avoids_advice_phrases() -> None:
    rendered = str(build_japan_resident_integrated_risk_context(_inputs()))

    for forbidden in ("買うべき", "今が買い", "安全", "利益が出る", "確実", "推奨銘柄"):
        assert forbidden not in rendered
