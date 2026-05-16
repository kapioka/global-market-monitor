from __future__ import annotations

from project.investment_candidates import build_investment_candidates


def test_build_investment_candidates_returns_priority_tier():
    result = build_investment_candidates(
        {
            "regime": {"regime_label": "risk_on"},
            "spot_signal": {"action": "buy_window"},
            "data_reliability": {"level": "high", "decision_allowed": True},
            "alerts": [],
            "asset_compare": [
                {"asset_class": "US_Stocks", "ticker": "SPY", "ticker_name_ja": "米国大型株ETF", "momentum_12w": 0.12}
            ],
            "sector_rotation": {"table": [{"ticker": "XLE", "sector_name_ja": "エネルギー", "return_12w": 0.14, "rotation_phase_ja": "先導"}]},
        }
    )

    assert result["tier"] == "priority"
    assert result["label"] == "優先候補"
    assert len(result["candidate_tickers"]) == 2


def test_build_investment_candidates_returns_watch_tier():
    result = build_investment_candidates(
        {
            "regime": {"regime_label": "transition"},
            "spot_signal": {"action": "watch"},
            "data_reliability": {"level": "medium", "decision_allowed": True},
            "alerts": [],
            "asset_compare": [],
            "sector_rotation": {"table": [{"ticker": "XLV", "sector_name_ja": "ヘルスケア", "return_12w": 0.05, "rotation_phase_ja": "改善"}]},
        }
    )

    assert result["tier"] == "watch"
    assert result["label"] == "観察候補"
    assert result["preferred_sector"]["ticker"] == "XLV"


def test_build_investment_candidates_returns_none_when_guarded():
    result = build_investment_candidates(
        {
            "regime": {"regime_label": "data_unavailable"},
            "spot_signal": {"action": "wait"},
            "data_reliability": {"level": "low", "decision_allowed": False},
            "alerts": [{"category": "market", "severity": "high"}],
            "asset_compare": [],
            "sector_rotation": {"table": []},
        }
    )

    assert result["tier"] == "none"
    assert result["label"] == "候補なし"
    assert result["candidate_tickers"] == []


def test_build_investment_candidates_keeps_candidates_under_high_market_alert():
    result = build_investment_candidates(
        {
            "regime": {"regime_label": "risk_on"},
            "spot_signal": {"action": "buy_window"},
            "data_reliability": {"level": "high", "decision_allowed": True},
            "alerts": [{"category": "market", "severity": "high"}],
            "asset_compare": [
                {"asset_class": "US_Stocks", "ticker": "SPY", "ticker_name_ja": "米国大型株ETF", "momentum_12w": 0.12}
            ],
            "sector_rotation": {"table": [{"ticker": "XLE", "sector_name_ja": "エネルギー", "return_12w": 0.14, "rotation_phase_ja": "先導"}]},
        }
    )

    assert result["tier"] == "priority"
    assert len(result["candidate_tickers"]) == 2
    assert any("参考候補" in reason for reason in result["rationale"])


def test_build_investment_candidates_returns_reference_when_wait_but_comparison_is_available():
    result = build_investment_candidates(
        {
            "regime": {"regime_label": "inflation_shock"},
            "spot_signal": {"action": "wait"},
            "data_reliability": {"level": "high", "decision_allowed": True},
            "alerts": [{"category": "market", "severity": "high"}],
            "asset_compare": [
                {"asset_class": "US_Stocks", "ticker": "SPY", "ticker_name_ja": "米国大型株ETF", "momentum_12w": 0.12}
            ],
            "sector_rotation": {"table": [{"ticker": "XLE", "sector_name_ja": "エネルギー", "return_12w": 0.14, "rotation_phase_ja": "先導"}]},
        }
    )

    assert result["tier"] == "reference"
    assert result["label"] == "参考候補"
    assert len(result["candidate_tickers"]) == 2
    assert any("参考候補" in reason for reason in result["rationale"])
