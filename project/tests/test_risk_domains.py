from __future__ import annotations

from project.risk_domains import evaluate_risk_domains


def _row(ticker: str, level: str, pressure: float, **extra):
    return {
        "ticker": ticker,
        "line_level": level,
        "pressure_score": pressure,
        "quality_flags": ["valid"],
        "stage_eligible": True,
        "limitations": [],
        **extra,
    }


def test_domain_engine_counts_correlated_credit_inputs_as_one_domain():
    result = evaluate_risk_domains(
        stress_monitor=[
            _row("HYG", "warning", 0.4),
            _row("LQD", "warning", 0.35),
            _row("HYG/LQD", "danger", 0.7),
            _row("SPY", "normal", 0.0),
            _row("^VIX", "normal", 0.0),
            _row("^MOVE", "normal", 0.0),
            _row("^TNX", "normal", 0.0),
            _row("DX-Y.NYB", "normal", 0.0),
            _row("CL=F", "normal", 0.0),
        ],
        credit_monitor=[],
        inflation_monitor=[],
    )

    credit = next(domain for domain in result["domains"] if domain["domain_id"] == "credit")
    assert credit["stage"] == "danger"
    assert credit["confidence"] == "fallback"
    assert result["independent_stressed_domain_count"] == 1


def test_domain_engine_prefers_official_oas_over_hyg_lqd_proxy():
    result = evaluate_risk_domains(
        stress_monitor=[
            _row("FRED:BAMLH0A0HYM2", "warning", 0.5),
            _row("FRED:BAMLC0A0CM", "normal", 0.1),
            _row("HYG/LQD", "extreme", 1.0),
            _row("SPY", "normal", 0.0),
            _row("^VIX", "normal", 0.0),
            _row("^MOVE", "normal", 0.0),
            _row("^TNX", "normal", 0.0),
            _row("DX-Y.NYB", "normal", 0.0),
            _row("CL=F", "normal", 0.0),
        ],
        credit_monitor=[],
        inflation_monitor=[],
    )

    credit = next(domain for domain in result["domains"] if domain["domain_id"] == "credit")
    assert credit["stage"] == "warning"
    assert credit["confidence"] == "high"
    assert credit["evidence"][0]["ticker"] == "FRED:BAMLH0A0HYM2"
    assert "HYG/LQD" not in [row["ticker"] for row in credit["evidence"]]


def test_credit_domain_distinguishes_available_unscored_oas_from_missing_source():
    official_oas = {"FRED:BAMLH0A0HYM2", "FRED:BAMLC0A0CM"}
    result = evaluate_risk_domains(
        stress_monitor=[
            _row("HYG/LQD", "normal", 0.0),
            _row("SPY", "normal", 0.0),
            _row("^VIX", "normal", 0.0),
            _row("^MOVE", "normal", 0.0),
            _row("^TNX", "normal", 0.0),
            _row("DX-Y.NYB", "normal", 0.0),
            _row("CL=F", "normal", 0.0),
        ],
        credit_monitor=[],
        inflation_monitor=[],
        available_series=official_oas,
    )

    credit = next(domain for domain in result["domains"] if domain["domain_id"] == "credit")
    assert credit["confidence"] == "fallback"
    assert credit["official_series_availability"] == {
        "available": ["FRED:BAMLH0A0HYM2", "FRED:BAMLC0A0CM"],
        "missing": [],
        "stage_scored": False,
        "usage": "diagnostic_coverage_only",
    }
    assert "official OAS unavailable" not in credit["limitations"]
    assert any("available for diagnostic coverage" in item for item in credit["limitations"])


def test_wti_and_brent_count_as_one_commodity_domain():
    result = evaluate_risk_domains(
        stress_monitor=[
            _row("SPY", "normal", 0.0),
            _row("^VIX", "normal", 0.0),
            _row("^MOVE", "normal", 0.0),
            _row("HYG/LQD", "normal", 0.0),
            _row("^TNX", "normal", 0.0),
            _row("DX-Y.NYB", "normal", 0.0),
            _row("CL=F", "warning", 0.4),
            _row("BZ=F", "danger", 0.7),
        ],
        credit_monitor=[],
        inflation_monitor=[],
    )

    commodity = next(domain for domain in result["domains"] if domain["domain_id"] == "commodity_inflation")
    assert commodity["stage"] == "danger"
    assert result["independent_stressed_domain_count"] == 1
    assert any("one commodity domain vote" in item for item in commodity["limitations"])


def test_commodity_domain_uses_oil_context_instead_of_raw_oil_pressure_score():
    result = evaluate_risk_domains(
        stress_monitor=[
            _row("SPY", "warning", 0.4, change_4w=-0.08),
            _row("^VIX", "normal", 0.0),
            _row("^MOVE", "normal", 0.0),
            _row("HYG/LQD", "warning", 0.4),
            _row("^TNX", "normal", 0.0),
            _row("DX-Y.NYB", "normal", 0.0),
            _row(
                "CL=F",
                "normal",
                0.0,
                oil_context={
                    "overall_status": "demand_watch",
                    "inflation_pressure_score": 0.0,
                    "demand_collapse_score": 62.0,
                    "risk_signal_allowed": True,
                    "quality_flags": ["valid"],
                    "limitations": [],
                    "reason": "oil drop confirmed by equity and credit",
                },
            ),
        ],
        credit_monitor=[],
        inflation_monitor=[],
    )

    commodity = next(domain for domain in result["domains"] if domain["domain_id"] == "commodity_inflation")
    assert commodity["stage"] == "warning"
    assert commodity["score_0_100"] == 62.0
    assert commodity["evidence"][0]["ticker"] == "oil_context"


def test_gold_momentum_only_does_not_raise_stage_or_domain_count():
    result = evaluate_risk_domains(
        stress_monitor=[
            _row("SPY", "normal", 0.0, change_1w=0.02),
            _row("^VIX", "normal", 0.0),
            _row("^MOVE", "normal", 0.0),
            _row("HYG/LQD", "normal", 0.0),
            _row("^TNX", "normal", 0.0),
            _row("DX-Y.NYB", "normal", 0.0),
            _row("CL=F", "normal", 0.0),
        ],
        credit_monitor=[],
        inflation_monitor=[{"ticker": "GC=F", "change_1w": 0.04, "quality_flags": ["valid"]}],
    )

    assert result["stage"] == "normal"
    assert result["independent_stressed_domain_count"] == 0
    assert result["corroborative_evidence"] == [{"type": "gold_momentum", "stage_effect": "none", "gold_return": 0.04}]


def test_gold_defensive_confirmation_is_corroborative_only():
    result = evaluate_risk_domains(
        stress_monitor=[
            _row("SPY", "warning", 0.4, change_1w=-0.04),
            _row("^VIX", "warning", 0.5),
            _row("^MOVE", "normal", 0.0),
            _row("HYG/LQD", "normal", 0.0),
            _row("^TNX", "normal", 0.0),
            _row("DX-Y.NYB", "normal", 0.0),
            _row("CL=F", "normal", 0.0),
        ],
        credit_monitor=[],
        inflation_monitor=[{"ticker": "GC=F", "change_1w": 0.05, "quality_flags": ["valid"]}],
    )

    assert result["independent_stressed_domain_count"] == 2
    assert any(row["type"] == "gold_defensive_confirmation" for row in result["corroborative_evidence"])
    assert all(row["stage_effect"] != "independent_vote" for row in result["corroborative_evidence"])


def test_missing_domains_reduce_strict_judgement_without_neutral_substitution():
    result = evaluate_risk_domains(stress_monitor=[_row("SPY", "normal", 0.0)], credit_monitor=[], inflation_monitor=[])

    assert result["strict_judgement_available"] is False
    assert result["eligible_domain_coverage"] < 0.75
    assert result["composite_domain_score"] == 0.0
    assert "minimum eligible domain coverage not met" in result["limitations"]


def test_single_isolated_domain_does_not_raise_global_danger():
    result = evaluate_risk_domains(
        stress_monitor=[
            _row("SPY", "danger", 0.9),
            _row("^VIX", "normal", 0.0),
            _row("^MOVE", "normal", 0.0),
            _row("HYG/LQD", "normal", 0.0),
            _row("^TNX", "normal", 0.0),
            _row("DX-Y.NYB", "normal", 0.0),
            _row("CL=F", "normal", 0.0),
        ],
        credit_monitor=[],
        inflation_monitor=[],
    )

    assert result["global_stage_policy"]["max_domain_rank"] == 2
    assert result["stage"] == "warning"
    assert "single stressed domain capped at warning" in result["global_stage_policy"]["caps"]


def test_multiple_nonfallback_domains_can_raise_global_danger():
    result = evaluate_risk_domains(
        stress_monitor=[
            _row("SPY", "danger", 0.8),
            _row("^VIX", "warning", 0.5),
            _row("^MOVE", "normal", 0.0),
            _row("HYG/LQD", "normal", 0.0),
            _row("^TNX", "normal", 0.0),
            _row("DX-Y.NYB", "normal", 0.0),
            _row("CL=F", "normal", 0.0),
        ],
        credit_monitor=[],
        inflation_monitor=[],
    )

    assert result["global_stage_policy"]["nonfallback_stressed_domain_count"] == 2
    assert result["stage"] == "danger"


def test_fallback_only_stress_cannot_independently_produce_highest_stages():
    result = evaluate_risk_domains(
        stress_monitor=[
            _row("SPY", "normal", 0.0),
            _row("^VIX", "normal", 0.0),
            _row("^MOVE", "normal", 0.0),
            _row("HYG/LQD", "extreme", 1.0),
            _row("^TNX", "normal", 0.0),
            _row("DX-Y.NYB", "normal", 0.0),
            _row("CL=F", "normal", 0.0),
        ],
        credit_monitor=[],
        inflation_monitor=[],
    )

    assert result["domains"][3]["domain_id"] == "credit"
    assert result["domains"][3]["confidence"] == "fallback"
    assert result["stage"] == "warning"
    assert "fallback-only stressed evidence capped at warning" in result["global_stage_policy"]["caps"]


def test_validated_shock_override_is_explicit_and_configurable():
    result = evaluate_risk_domains(
        stress_monitor=[
            _row("SPY", "normal", 0.0),
            _row("^VIX", "extreme", 1.0),
            _row("^MOVE", "normal", 0.0),
            _row("HYG/LQD", "normal", 0.0),
            _row("^TNX", "normal", 0.0),
            _row("DX-Y.NYB", "normal", 0.0),
            _row("CL=F", "normal", 0.0),
        ],
        credit_monitor=[],
        inflation_monitor=[],
        config={
            "risk_engine_v2": {
                "global_stage_policy": {
                    "shock_overrides": [
                        {
                            "enabled": True,
                            "domain_id": "equity_volatility",
                            "domain_stage_at_least": "extreme",
                            "global_stage": "danger",
                            "reason": "validated volatility shock",
                        }
                    ]
                }
            }
        },
    )

    assert result["stage"] == "danger"
    assert result["global_stage_policy"]["shock_override"]["reason"] == "validated volatility shock"
