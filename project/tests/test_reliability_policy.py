from __future__ import annotations

import pandas as pd

from project.data_fetcher import FetchResult
from project.reliability_policy import apply_reliability_policy, assess_data_reliability, critical_tickers


def _fetch(source: str, acquisition_log: list[dict[str, str]], summary: dict[str, object] | None = None) -> FetchResult:
    return FetchResult(
        prices=pd.DataFrame({"SPY": [100.0]}),
        warnings=[],
        source=source,
        acquisition_log=acquisition_log,
        diagnostics={"summary": summary or {}},
    )


def _config() -> dict[str, object]:
    return {
        "tickers": {
            "global_equities": {"World": "ACWI"},
            "credit": {"HighYield": "HYG", "InvestmentGrade": "LQD"},
            "japan": {"usd_jpy": "USDJPY=X"},
        }
    }


def test_sample_source_is_diagnostic_only():
    fetch = _fetch(
        "sample",
        [{"requested_ticker": "SPY", "status": "sample_fallback"}],
        {"requested_count": 1, "sample_fallback_count": 1},
    )

    result = assess_data_reliability(_config(), fetch)

    assert result["level"] == "diagnostic"
    assert result["decision_allowed"] is False
    assert result["max_action"] == "diagnostic_only"
    assert result["confidence_cap"] == 0.0
    assert result["watermark_required"] is True
    assert "sample_only" in result["blocking_reasons"]


def test_live_ratio_below_sixty_forces_wait():
    fetch = _fetch(
        "mixed",
        [
            {"requested_ticker": "SPY", "status": "ok"},
            {"requested_ticker": "XLE", "status": "unavailable"},
            {"requested_ticker": "GLD", "status": "unavailable"},
        ],
        {"requested_count": 3, "unavailable_count": 2},
    )

    result = assess_data_reliability(_config(), fetch)

    assert result["decision_allowed"] is False
    assert result["max_action"] == "wait"
    assert result["confidence_cap"] == 0.25
    assert "live_ratio_below_60" in result["blocking_reasons"]


def test_critical_failure_caps_action_to_watch():
    fetch = _fetch(
        "mixed",
        [
            {"requested_ticker": "ACWI", "status": "sample_fallback"},
            {"requested_ticker": "HYG", "status": "ok"},
            {"requested_ticker": "LQD", "status": "ok"},
            {"requested_ticker": "USDJPY=X", "status": "ok"},
        ],
        {"requested_count": 4, "sample_fallback_count": 1},
    )

    result = assess_data_reliability(_config(), fetch)

    assert result["decision_allowed"] is True
    assert result["max_action"] == "watch"
    assert result["confidence_cap"] == 0.45
    assert result["critical_failures"] == ["ACWI"]
    assert "critical_series_unavailable" in result["degrade_reasons"]


def test_noncritical_sample_fallback_caps_action_to_watch():
    fetch = _fetch(
        "mixed",
        [
            {"requested_ticker": "SPY", "status": "ok"},
            {"requested_ticker": "XLE", "status": "sample_fallback"},
            {"requested_ticker": "HYG", "status": "ok"},
            {"requested_ticker": "LQD", "status": "ok"},
        ],
        {"requested_count": 4, "sample_fallback_count": 1},
    )

    result = assess_data_reliability(_config(), fetch)

    assert result["decision_allowed"] is True
    assert result["max_action"] == "watch"
    assert result["confidence_cap"] == 0.45
    assert result["critical_failures"] == []
    assert "sample_fallback_present" in result["degrade_reasons"]


def test_proxy_only_keeps_buy_window_with_confidence_cap():
    fetch = _fetch(
        "mixed",
        [
            {"requested_ticker": "SPY", "status": "ok"},
            {"requested_ticker": "XLE", "status": "proxy_fallback"},
            {"requested_ticker": "HYG", "status": "ok"},
            {"requested_ticker": "LQD", "status": "ok"},
            {"requested_ticker": "USDJPY=X", "status": "ok"},
        ],
        {"requested_count": 5, "proxy_fallback_count": 1},
    )

    result = assess_data_reliability(_config(), fetch)

    assert result["decision_allowed"] is True
    assert result["max_action"] == "buy_window"
    assert result["confidence_cap"] == 0.75
    assert "proxy_fallback_present" in result["degrade_reasons"]


def test_clean_live_data_allows_buy_window():
    fetch = _fetch(
        "yfinance",
        [
            {"requested_ticker": "SPY", "status": "ok"},
            {"requested_ticker": "ACWI", "status": "ok"},
            {"requested_ticker": "HYG", "status": "ok"},
            {"requested_ticker": "LQD", "status": "ok"},
            {"requested_ticker": "USDJPY=X", "status": "ok"},
        ],
        {"requested_count": 5},
    )

    result = assess_data_reliability(_config(), fetch)

    assert result["level"] == "high"
    assert result["decision_allowed"] is True
    assert result["max_action"] == "buy_window"
    assert result["confidence_cap"] == 1.0


def test_critical_tickers_include_configured_credit_and_japan_series():
    result = critical_tickers(_config())

    assert {"ACWI", "SPY", "HYG", "LQD", "USDJPY=X"}.issubset(result)


def test_apply_reliability_policy_caps_action_and_keeps_explicit_fields():
    decision = {
        "action": "buy_window",
        "raw_action": "buy_window",
        "confidence": 0.82,
        "raw_confidence": 0.82,
        "mode": "evidence_confirmed",
        "reason_path": ["confirmed", "none"],
    }
    reliability = {
        "max_action": "watch",
        "confidence_cap": 0.45,
        "blocking_reasons": [],
        "degrade_reasons": ["sample_fallback_present"],
        "critical_failures": [],
        "live_ratio": 0.91,
        "sample_fallback_count": 1,
        "proxy_fallback_count": 0,
        "unavailable_count": 0,
    }

    result = apply_reliability_policy(decision, reliability)

    assert result["original_action"] == "buy_window"
    assert result["final_action"] == "watch"
    assert result["action"] == "watch"
    assert result["original_confidence"] == 0.82
    assert result["final_confidence"] == 0.45
    assert result["cap_level"] == "watch"
    assert result["policy_triggered"] is True
    assert result["policy_reasons"] == ["sample_fallback_present"]
    assert result["sample_fallback_count"] == 1


def test_apply_reliability_policy_allows_clean_buy_window_without_trigger():
    decision = {
        "action": "buy_window",
        "raw_action": "buy_window",
        "confidence": 0.72,
        "raw_confidence": 0.72,
    }
    reliability = {
        "max_action": "buy_window",
        "confidence_cap": 1.0,
        "degrade_reasons": ["live_data_sufficient"],
        "live_ratio": 1.0,
    }

    result = apply_reliability_policy(decision, reliability)

    assert result["final_action"] == "buy_window"
    assert result["final_confidence"] == 0.72
    assert result["policy_triggered"] is False
