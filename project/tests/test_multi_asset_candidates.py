from __future__ import annotations

from project.multi_asset_candidates import build_multi_asset_candidates


def _inputs() -> dict:
    return {
        "asset_map": {"US_Stocks": "SPY", "Gold": "GLD", "Bonds": "AGG", "Inflation_Bonds": "TIP"},
        "availability_map": {
            "SPY": {"status": "ok"},
            "GLD": {"status": "ok"},
            "AGG": {"status": "ok"},
            "TIP": {"status": "ok"},
        },
        "asset_compare": [
            {"asset_class": "US_Stocks", "ticker": "SPY", "ticker_name_ja": "米国大型株ETF", "momentum_12w": 0.12},
            {"asset_class": "Gold", "ticker": "GLD", "ticker_name_ja": "金ETF", "momentum_12w": 0.04},
            {"asset_class": "Bonds", "ticker": "AGG", "ticker_name_ja": "総合債券ETF", "momentum_12w": 0.02},
        ],
        "inflation_monitor": [{"ticker": "GC=F", "ticker_name_ja": "金先物", "change_4w": 0.03}],
        "credit_monitor": [{"ticker": "LQD", "ticker_name_ja": "投資適格社債ETF", "change_4w": 0.01}],
        "investment_candidates": {
            "tier": "watch",
            "preferred_asset_class": {"asset_class": "US_Stocks", "ticker": "SPY", "ticker_name_ja": "米国大型株ETF"},
        },
        "data_reliability": {"decision_allowed": True},
        "risk_lines": {"stage_key": "normal"},
    }


def test_build_multi_asset_candidates_returns_japan_resident_asset_classes() -> None:
    result = build_multi_asset_candidates(_inputs())

    classes = [row["asset_class"] for row in result["candidates"]]
    assert classes == ["equity", "gold", "bond", "bond_jpy", "jp_equity", "reit_jp", "cash"]
    assert result["affects_final_action"] is False
    assert result["affects_buy_readiness_score"] is False
    assert "japan_resident_taxonomy" in result
    assert "japan_resident_data_contract" in result


def test_gold_and_bond_do_not_mix_with_equity_candidate_role() -> None:
    result = build_multi_asset_candidates(_inputs())
    by_class = {row["asset_class"]: row for row in result["candidates"]}

    assert by_class["equity"]["role"] == "growth"
    assert by_class["gold"]["role"] == "defensive"
    assert by_class["bond"]["role"] == "diversification"
    assert by_class["gold"]["symbol"] == "GLD"
    assert by_class["bond"]["symbol"] == "AGG"
    assert "reason_category" not in by_class["equity"]
    assert by_class["gold"]["reason_category"] == "defensive_context"
    assert by_class["bond"]["reason_category"] == "rate_sensitive_context"
    assert by_class["gold"]["must_not_affect_final_action"] is True
    assert by_class["bond"]["must_not_affect_buy_readiness_score"] is True


def test_missing_market_data_still_builds_display_payload() -> None:
    result = build_multi_asset_candidates(
        {
            "asset_map": {},
            "availability_map": {},
            "asset_compare": [],
            "inflation_monitor": [],
            "credit_monitor": [],
            "investment_candidates": {},
            "data_reliability": {"decision_allowed": False},
            "risk_lines": {},
        }
    )

    by_class = {row["asset_class"]: row for row in result["candidates"]}
    assert by_class["equity"]["status"] == "not_available"
    assert by_class["gold"]["status"] == "unavailable"
    assert by_class["bond"]["status"] == "unavailable"
    assert by_class["cash"]["status"] == "wait"
    assert by_class["gold"]["reason_category"] == "insufficient_data"
    assert by_class["bond"]["reason_category"] == "insufficient_data"
    assert by_class["cash"]["reason_category"] == "wait_context"
    assert result["disclaimer"]


def test_signal_connection_adds_non_impact_fields_to_non_equity_candidates() -> None:
    result = build_multi_asset_candidates(_inputs())
    by_class = {row["asset_class"]: row for row in result["candidates"]}

    for asset_class in ("gold", "bond", "cash"):
        row = by_class[asset_class]
        assert row["status"] in {"informational", "watch", "unavailable", "wait"}
        assert row["caution_required"] is True
        assert row["must_not_affect_final_action"] is True
        assert row["must_not_affect_buy_readiness_score"] is True


def test_japan_resident_context_rows_are_display_only_and_conservative() -> None:
    result = build_multi_asset_candidates(_inputs())
    by_class = {row["asset_class"]: row for row in result["candidates"]}

    for asset_class in ("bond_jpy", "jp_equity", "reit_jp"):
        row = by_class[asset_class]
        assert row["status"] in {"informational", "unavailable", "watch"}
        assert row["must_not_affect_final_action"] is True
        assert row["must_not_affect_buy_readiness_score"] is True
        assert row["japan_resident_must_not_affect_final_action"] is True
        assert row["japan_resident_must_not_affect_buy_readiness_score"] is True
        assert "japan_resident_context_score" in row
        assert row["japan_resident_caution_required"] is True

    assert by_class["bond_jpy"]["status"] == "unavailable"
    assert by_class["reit_jp"]["status"] == "unavailable"


def test_japan_resident_context_uses_existing_japan_proxy_when_available() -> None:
    inputs = _inputs()
    inputs["japan_tickers"] = {"topix_proxy": "1306.T"}
    inputs["availability_map"]["1306.T"] = {"status": "ok"}
    inputs["asset_compare"].append(
        {"asset_class": "Japan_Stocks", "ticker": "1306.T", "ticker_name_ja": "TOPIX連動ETF", "momentum_12w": 0.03}
    )

    result = build_multi_asset_candidates(inputs)
    jp_equity = {row["asset_class"]: row for row in result["candidates"]}["jp_equity"]

    assert jp_equity["symbol"] == "1306.T"
    assert jp_equity["display_name"] == "TOPIX連動ETF"
    assert jp_equity["source_data_available"] is True
    assert jp_equity["japan_resident_reason_category"] == "jp_equity_context"
    assert jp_equity["japan_resident_must_not_affect_final_action"] is True


def test_japan_resident_configured_bond_and_reit_tickers_feed_display_rows() -> None:
    inputs = _inputs()
    inputs["japan_tickers"] = {"jpy_bond_intermediate": "2510.T", "jp_reit_proxy": "1343.T", "gold_jpy_proxy": "1540.T"}
    inputs["availability_map"].update({"2510.T": {"status": "ok"}, "1343.T": {"status": "ok"}, "1540.T": {"status": "ok"}})

    result = build_multi_asset_candidates(inputs)
    by_class = {row["asset_class"]: row for row in result["candidates"]}

    assert by_class["bond_jpy"]["symbol"] == "2510.T"
    assert by_class["bond_jpy"]["source_data_available"] is True
    assert by_class["bond_jpy"]["japan_resident_reason_category"] == "jpy_rate_context"
    assert by_class["reit_jp"]["symbol"] == "1343.T"
    assert by_class["reit_jp"]["source_data_available"] is True
    assert by_class["reit_jp"]["japan_resident_reason_category"] == "jp_reit_context"
    assert by_class["gold"]["japan_resident_context_status"] in {"informational", "watch"}
    assert by_class["gold"]["japan_resident_context_components"]["jpy_relevance"] == 12
    assert by_class["bond_jpy"]["japan_resident_must_not_affect_buy_readiness_score"] is True
    assert by_class["reit_jp"]["japan_resident_must_not_affect_final_action"] is True


def test_domestic_market_metrics_feed_japan_resident_rows_without_acquisition_only_signal() -> None:
    inputs = _inputs()
    inputs["japan_tickers"] = {"jpy_bond_intermediate": "2510.T", "jp_reit_proxy": "1343.T", "gold_jpy_proxy": "1540.T"}
    inputs["domestic_market_metrics"] = {
        "by_symbol": {
            "2510.T": {
                "symbol": "2510.T",
                "is_available": True,
                "current_value": 90.0,
                "change_4w": -4.2,
                "change_12w": -9.1,
                "max_drawdown": -12.0,
                "trend_label": "weakening",
            },
            "1343.T": {
                "symbol": "1343.T",
                "is_available": True,
                "current_value": 88.0,
                "change_4w": -5.5,
                "change_12w": -10.0,
                "max_drawdown": -18.0,
                "trend_label": "weakening",
            },
            "1540.T": {"symbol": "1540.T", "is_available": True, "current_value": 111.0, "change_4w": 2.0},
        }
    }

    result = build_multi_asset_candidates(inputs)
    by_class = {row["asset_class"]: row for row in result["candidates"]}

    assert by_class["bond_jpy"]["metrics"]["current_value"] == 90.0
    assert by_class["bond_jpy"]["source_data_available"] is True
    assert by_class["reit_jp"]["metrics"]["trend_label"] == "weakening"
    assert by_class["gold"]["japan_resident_context_components"]["trend"] >= 0
    assert by_class["bond_jpy"]["japan_resident_must_not_affect_final_action"] is True


def test_official_macro_context_feeds_display_only_japan_rows() -> None:
    inputs = _inputs()
    inputs["japan_tickers"] = {"jpy_bond_intermediate": "2510.T", "jp_reit_proxy": "1343.T", "gold_jpy_proxy": "1540.T"}
    inputs["availability_map"].update({"2510.T": {"status": "ok"}, "1343.T": {"status": "ok"}, "1540.T": {"status": "ok"}})
    inputs["japan_resident_context"] = {
        "jgb_yields": {"jgb_10y": 1.08, "jgb_curve_10y_2y": 0.74},
        "inflation": {"jp_cpi_yoy": 2.7, "jp_core_cpi_yoy": 2.4, "jp_cpi_trend": "rising"},
        "domestic_rates": {"boj_policy_rate": 0.25, "boj_call_rate": 0.28, "domestic_rate_context": "rising"},
        "macro_sources": {"japan_cpi": {"status": "ok"}},
    }

    result = build_multi_asset_candidates(inputs)
    by_class = {row["asset_class"]: row for row in result["candidates"]}

    assert by_class["bond_jpy"]["japan_resident_context_components"]["domestic_rate"] < 0
    assert by_class["reit_jp"]["japan_resident_context_components"]["domestic_rate"] < 0
    assert by_class["gold"]["japan_resident_context_components"]["inflation"] > 0
    assert by_class["cash"]["japan_resident_context_components"]["domestic_rate"] > 0
    assert by_class["bond_jpy"]["japan_resident_must_not_affect_final_action"] is True
    assert result["affects_buy_readiness_score"] is False


def test_japan_resident_unavailable_configured_series_stay_data_unavailable() -> None:
    inputs = _inputs()
    inputs["japan_tickers"] = {"jpy_bond_intermediate": "2510.T", "jp_reit_proxy": "1343.T", "gold_jpy_proxy": "1540.T"}
    inputs["acquisition_log"] = [
        {"requested_ticker": "2510.T", "used_ticker": None, "status": "unavailable"},
        {"requested_ticker": "1343.T", "used_ticker": None, "status": "unavailable"},
        {"requested_ticker": "1540.T", "used_ticker": None, "status": "unavailable"},
    ]

    result = build_multi_asset_candidates(inputs)
    by_class = {row["asset_class"]: row for row in result["candidates"]}

    assert by_class["bond_jpy"]["symbol"] == "2510.T"
    assert by_class["bond_jpy"]["source_data_available"] is False
    assert by_class["bond_jpy"]["japan_resident_context_status"] == "unavailable"
    assert by_class["reit_jp"]["symbol"] == "1343.T"
    assert by_class["reit_jp"]["source_data_available"] is False
    assert by_class["reit_jp"]["japan_resident_context_status"] == "unavailable"


def test_japan_resident_sample_fallback_series_are_reference_display_not_missing() -> None:
    inputs = _inputs()
    inputs["japan_tickers"] = {"jpy_bond_intermediate": "2510.T", "jp_reit_proxy": "1343.T", "gold_jpy_proxy": "1540.T"}
    inputs["acquisition_log"] = [
        {"requested_ticker": "2510.T", "used_ticker": "2510.T", "status": "sample_fallback"},
        {"requested_ticker": "1343.T", "used_ticker": "1343.T", "status": "sample_fallback"},
        {"requested_ticker": "1540.T", "used_ticker": "1540.T", "status": "sample_fallback"},
    ]

    result = build_multi_asset_candidates(inputs)
    by_class = {row["asset_class"]: row for row in result["candidates"]}

    assert by_class["bond_jpy"]["source_data_available"] is True
    assert by_class["bond_jpy"]["japan_resident_context_status"] == "informational"
    assert by_class["reit_jp"]["source_data_available"] is True
    assert by_class["reit_jp"]["japan_resident_context_status"] == "informational"
    assert by_class["gold"]["japan_resident_context_status"] == "informational"


def test_gold_available_without_asset_compare_uses_monitor_as_watch_context() -> None:
    inputs = _inputs()
    inputs["asset_compare"] = [row for row in inputs["asset_compare"] if row["asset_class"] != "Gold"]
    inputs["asset_map"] = {}
    inputs["availability_map"] = {"GC=F": {"status": "ok"}}

    result = build_multi_asset_candidates(inputs)
    gold = {row["asset_class"]: row for row in result["candidates"]}["gold"]

    assert gold["symbol"] == "GC=F"
    assert gold["status"] == "watch"
    assert gold["source_data_available"] is True
    assert gold["reason_category"] == "defensive_context"
    assert gold["must_not_affect_final_action"] is True


def test_bond_available_without_asset_compare_uses_credit_monitor_as_watch_context() -> None:
    inputs = _inputs()
    inputs["asset_compare"] = [row for row in inputs["asset_compare"] if row["asset_class"] != "Bonds"]
    inputs["asset_map"] = {}
    inputs["availability_map"] = {"LQD": {"status": "ok"}}

    result = build_multi_asset_candidates(inputs)
    bond = {row["asset_class"]: row for row in result["candidates"]}["bond"]

    assert bond["symbol"] == "LQD"
    assert bond["status"] == "watch"
    assert bond["source_data_available"] is True
    assert bond["reason_category"] == "rate_sensitive_context"
    assert bond["must_not_affect_buy_readiness_score"] is True


def test_mixed_partial_data_keeps_missing_asset_unavailable_and_cash_wait_state() -> None:
    inputs = _inputs()
    inputs["asset_compare"] = [
        {"asset_class": "Gold", "ticker": "GLD", "ticker_name_ja": "金ETF", "momentum_12w": 0.04},
        {"asset_class": "Commodities", "ticker": "DBC", "ticker_name_ja": "商品ETF"},
    ]
    inputs["asset_map"] = {"Gold": "GLD"}
    inputs["availability_map"] = {"GLD": {"status": "ok"}, "AGG": {"status": "unavailable"}}
    inputs["credit_monitor"] = []
    inputs["data_reliability"] = {"decision_allowed": False}

    result = build_multi_asset_candidates(inputs)
    by_class = {row["asset_class"]: row for row in result["candidates"]}

    assert by_class["gold"]["status"] == "watch"
    assert by_class["bond"]["status"] == "unavailable"
    assert by_class["bond"]["reason_category"] == "insufficient_data"
    assert by_class["cash"]["status"] == "wait"
    assert "Commodities" not in by_class


def test_missing_optional_fields_do_not_break_non_equity_signal_candidates() -> None:
    result = build_multi_asset_candidates(
        {
            "asset_map": {"Gold": "GLD", "Bonds": "AGG"},
            "availability_map": {"GLD": {"status": "ok"}, "AGG": {"status": "ok"}},
            "asset_compare": [{"asset_class": "Gold"}, {"asset_class": "Bonds"}],
            "inflation_monitor": [],
            "credit_monitor": [],
            "investment_candidates": {},
            "data_reliability": {"decision_allowed": True},
            "risk_lines": {"stage_key": "normal"},
        }
    )
    by_class = {row["asset_class"]: row for row in result["candidates"]}

    assert by_class["gold"]["display_name"] == "ゴールド"
    assert by_class["bond"]["display_name"] == "米国債券ETF"
    assert by_class["gold"]["status"] == "watch"
    assert by_class["bond"]["status"] == "watch"


def test_existing_acquisition_log_can_feed_gold_and_bond_candidates_without_asset_compare() -> None:
    result = build_multi_asset_candidates(
        {
            "asset_map": {},
            "availability_map": {},
            "asset_compare": [],
            "inflation_monitor": [],
            "credit_monitor": [],
            "acquisition_log": [
                {
                    "requested_ticker": "GLD",
                    "requested_ticker_name_ja": "金ETF",
                    "used_ticker": "GLD",
                    "used_ticker_name_ja": "金ETF",
                    "status": "ok",
                },
                {
                    "requested_ticker": "TIP",
                    "requested_ticker_name_ja": "米国物価連動国債ETF",
                    "used_ticker": "TIP",
                    "used_ticker_name_ja": "米国物価連動国債ETF",
                    "status": "ok",
                },
            ],
            "investment_candidates": {},
            "data_reliability": {"decision_allowed": True},
            "risk_lines": {"stage_key": "normal"},
        }
    )
    by_class = {row["asset_class"]: row for row in result["candidates"]}

    assert by_class["gold"]["symbol"] == "GLD"
    assert by_class["gold"]["display_name"] == "金ETF"
    assert by_class["gold"]["status"] == "watch"
    assert by_class["gold"]["source_data_available"] is True
    assert by_class["bond"]["symbol"] == "TIP"
    assert by_class["bond"]["display_name"] == "米国物価連動国債ETF"
    assert by_class["bond"]["status"] == "watch"
    assert by_class["bond"]["source_data_available"] is True
    assert by_class["gold"]["must_not_affect_final_action"] is True
    assert by_class["bond"]["must_not_affect_buy_readiness_score"] is True


def test_acquisition_log_unavailable_status_stays_conservative() -> None:
    result = build_multi_asset_candidates(
        {
            "asset_map": {},
            "availability_map": {},
            "asset_compare": [],
            "inflation_monitor": [],
            "credit_monitor": [],
            "acquisition_log": [
                {"requested_ticker": "GLD", "used_ticker": "GLD", "status": "unavailable"},
                {"requested_ticker": "AGG", "used_ticker": "AGG", "status": "sample_fallback"},
            ],
            "investment_candidates": {},
            "data_reliability": {"decision_allowed": False},
            "risk_lines": {},
        }
    )
    by_class = {row["asset_class"]: row for row in result["candidates"]}

    assert by_class["gold"]["status"] == "unavailable"
    assert by_class["bond"]["status"] == "unavailable"
    assert by_class["gold"]["source_data_available"] is False
    assert by_class["bond"]["source_data_available"] is False
    assert by_class["cash"]["status"] == "wait"


def test_acquisition_log_failed_and_partial_statuses_do_not_create_watch_candidates() -> None:
    result = build_multi_asset_candidates(
        {
            "asset_map": {},
            "availability_map": {},
            "asset_compare": [],
            "inflation_monitor": [],
            "credit_monitor": [],
            "acquisition_log": [
                {
                    "requested_ticker": "GC=F",
                    "requested_ticker_name_ja": "金先物",
                    "used_ticker": "GC=F",
                    "used_ticker_name_ja": "金先物",
                    "status": "failed",
                },
                {
                    "requested_ticker": "LQD",
                    "requested_ticker_name_ja": "投資適格社債ETF",
                    "used_ticker": "LQD",
                    "used_ticker_name_ja": "投資適格社債ETF",
                    "status": "partial",
                },
            ],
            "investment_candidates": {},
            "data_reliability": {"decision_allowed": True},
            "risk_lines": {"stage_key": "normal"},
        }
    )
    by_class = {row["asset_class"]: row for row in result["candidates"]}

    assert by_class["gold"]["symbol"] == "GC=F"
    assert by_class["gold"]["status"] == "unavailable"
    assert by_class["gold"]["source_data_available"] is False
    assert by_class["bond"]["symbol"] == "LQD"
    assert by_class["bond"]["status"] == "unavailable"
    assert by_class["bond"]["source_data_available"] is False


def test_acquisition_log_uses_requested_ticker_match_and_used_ticker_display() -> None:
    result = build_multi_asset_candidates(
        {
            "asset_map": {},
            "availability_map": {},
            "asset_compare": [],
            "inflation_monitor": [],
            "credit_monitor": [],
            "acquisition_log": [
                {
                    "requested_ticker": "GLD",
                    "requested_ticker_name_ja": "金ETF",
                    "used_ticker": "IAU",
                    "used_ticker_name_ja": "金ETF代替",
                    "status": "ok",
                },
                {
                    "requested_ticker": "AGG",
                    "requested_ticker_name_ja": "総合債券ETF",
                    "used_ticker": "BND",
                    "used_ticker_name_ja": "総合債券ETF代替",
                    "status": "ok",
                },
            ],
            "investment_candidates": {},
            "data_reliability": {"decision_allowed": True},
            "risk_lines": {"stage_key": "normal"},
        }
    )
    by_class = {row["asset_class"]: row for row in result["candidates"]}

    assert by_class["gold"]["symbol"] == "IAU"
    assert by_class["gold"]["display_name"] == "金ETF代替"
    assert by_class["gold"]["status"] == "watch"
    assert by_class["bond"]["symbol"] == "BND"
    assert by_class["bond"]["display_name"] == "総合債券ETF代替"
    assert by_class["bond"]["status"] == "watch"


def test_availability_map_overrides_acquisition_log_status_for_known_symbol() -> None:
    result = build_multi_asset_candidates(
        {
            "asset_map": {"Gold": "GLD", "Bonds": "AGG"},
            "availability_map": {"GLD": {"status": "ok"}, "AGG": {"status": "unavailable"}},
            "asset_compare": [],
            "inflation_monitor": [],
            "credit_monitor": [],
            "acquisition_log": [
                {"requested_ticker": "GLD", "used_ticker": "GLD", "status": "failed"},
                {"requested_ticker": "AGG", "used_ticker": "AGG", "status": "ok"},
            ],
            "investment_candidates": {},
            "data_reliability": {"decision_allowed": True},
            "risk_lines": {"stage_key": "normal"},
        }
    )
    by_class = {row["asset_class"]: row for row in result["candidates"]}

    assert by_class["gold"]["status"] == "watch"
    assert by_class["gold"]["source_data_available"] is True
    assert by_class["bond"]["status"] == "unavailable"
    assert by_class["bond"]["source_data_available"] is False


def test_multi_asset_copy_avoids_forbidden_advice_phrases() -> None:
    result = build_multi_asset_candidates(_inputs())
    rendered = str(result)

    for forbidden in ("買うべき", "今が買い", "安全", "利益が出る", "確実", "推奨銘柄"):
        assert forbidden not in rendered
