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


def test_multi_asset_copy_avoids_forbidden_advice_phrases() -> None:
    result = build_multi_asset_candidates(_inputs())
    rendered = str(result)

    for forbidden in ("買うべき", "今が買い", "安全", "利益が出る", "確実", "推奨銘柄"):
        assert forbidden not in rendered
