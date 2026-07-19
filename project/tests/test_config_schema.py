from __future__ import annotations

import pytest

from project.config_schema import ConfigValidationError, validate_config


def _valid_config() -> dict:
    return {
        "schema_version": 1,
        "app": {"report_title": "test"},
        "paths": {"reports_dir": "project/reports"},
        "data": {"period_years": 10},
        "tickers": {
            "global_equities": {"ACWI": "ACWI", "SPY": "SPY"},
            "credit": {"HYG": "HYG", "LQD": "LQD"},
            "risk_indicators": {"VIX": "^VIX"},
            "japan": {"usd_jpy": "USDJPY=X"},
        },
        "thresholds": {"spot_score_buy": 0.65, "spot_score_watch": 0.45},
        "weights": {"trend": 1.0},
    }


def test_validate_config_accepts_existing_shape():
    assert validate_config(_valid_config()) == []


def test_validate_config_reports_missing_schema_version():
    config = _valid_config()
    del config["schema_version"]

    with pytest.raises(ConfigValidationError, match="schema_version"):
        validate_config(config)


def test_validate_config_reports_action_threshold_order():
    config = _valid_config()
    config["thresholds"]["spot_score_buy"] = 0.4

    with pytest.raises(ConfigValidationError, match="spot_score_buy"):
        validate_config(config)


def test_validate_config_reports_negative_weight():
    config = _valid_config()
    config["weights"]["trend"] = -0.1

    with pytest.raises(ConfigValidationError, match="weights.trend"):
        validate_config(config)


def test_validate_config_reports_missing_critical_ticker():
    config = _valid_config()
    del config["tickers"]["risk_indicators"]["VIX"]

    with pytest.raises(ConfigValidationError, match="critical tickers"):
        validate_config(config)


def test_validate_config_returns_unknown_key_warnings():
    config = _valid_config()
    config["experimental"] = {}

    warnings = validate_config(config)

    assert warnings == ["unknown top-level key `experimental` is present. Keep it only if downstream code intentionally uses it."]


def test_validate_config_accepts_risk_engine_v2_shadow_contract():
    config = _valid_config()
    config["risk_engine_v2"] = {
        "mode": "shadow",
        "minimum_eligible_domain_coverage": 0.75,
        "freshness_limits_calendar_days": {"daily": 5, "weekly": 14},
        "domain_weights": {
            "equity": 0.16,
            "equity_volatility": 0.14,
            "bond_volatility": 0.10,
            "credit": 0.20,
            "rates": 0.16,
            "usd_funding": 0.10,
            "commodity_inflation": 0.14,
        },
        "persistence": {"warning_entry_observations": 2, "warning_entry_window": 3, "danger_entry_consecutive": 2, "exit_consecutive": 2},
    }

    assert validate_config(config) == []


def test_validate_config_rejects_invalid_risk_engine_v2_mode():
    config = _valid_config()
    config["risk_engine_v2"] = {"mode": "production", "domain_weights": {"equity": 1.0}}

    with pytest.raises(ConfigValidationError, match="risk_engine_v2.mode"):
        validate_config(config)


def test_validate_config_rejects_domain_weights_that_do_not_sum_to_one():
    config = _valid_config()
    config["risk_engine_v2"] = {"mode": "shadow", "domain_weights": {"equity": 0.5, "credit": 0.4}}

    with pytest.raises(ConfigValidationError, match="domain_weights"):
        validate_config(config)
