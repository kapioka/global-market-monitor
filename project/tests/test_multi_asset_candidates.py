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


def test_build_multi_asset_candidates_returns_four_asset_classes() -> None:
    result = build_multi_asset_candidates(_inputs())

    classes = [row["asset_class"] for row in result["candidates"]]
    assert classes == ["equity", "gold", "bond", "cash"]
    assert result["affects_final_action"] is False
    assert result["affects_buy_readiness_score"] is False


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


def test_multi_asset_copy_avoids_forbidden_advice_phrases() -> None:
    result = build_multi_asset_candidates(_inputs())
    rendered = str(result)

    for forbidden in ("買うべき", "今が買い", "安全", "利益が出る", "確実", "推奨銘柄"):
        assert forbidden not in rendered
